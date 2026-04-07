'use server'

import { getServerSideAPI } from '@/utils/client/serverside'
import { CONFIG } from '@/utils/config'
import { getAuthenticatedUser } from '@/utils/user'
import { anthropic } from '@ai-sdk/anthropic'
import { google } from '@ai-sdk/google'
import { experimental_createMCPClient } from '@ai-sdk/mcp'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'
import { withTracing } from '@posthog/ai'
import {
  convertToModelMessages,
  generateObject,
  smoothStream,
  stepCountIs,
  streamText,
  tool,
  UIMessage,
} from 'ai'
import { cookies } from 'next/headers'
import { PostHog } from 'posthog-node'
import { z } from 'zod'

// ── PostHog Client ──

const phClient = process.env.NEXT_PUBLIC_POSTHOG_TOKEN
  ? new PostHog(process.env.NEXT_PUBLIC_POSTHOG_TOKEN!, {
      host: 'https://us.i.posthog.com',
    })
  : null

// ── System Prompts ──

const sharedSystemPrompt = `
You are a helpful assistant that helps users manage their file sharing on Rapidly.
You help users share files securely via P2P transfer, set pricing, and track activity.

# About Rapidly
Rapidly is a P2P encrypted file-sharing platform that makes it easy to share files securely with anyone.
Files are transferred directly between peers using WebRTC with end-to-end encryption.

<example prompt="What is Rapidly?">
Rapidly is a P2P encrypted file-sharing platform that lets you securely share files with anyone. You can:

 - Share files of any size via peer-to-peer transfer
 - Set optional pricing for paid file shares via Stripe
 - Set download limits on shares
 - Track downloads and payments
 - Customize your public page

What would you like to share today?
</example>

# File Sharing Setup
Rapidly makes it easy to share files with optional paid access.

## File Shares
A file share is a session where you send files directly to recipients via P2P transfer. Shares can be configured with:
 - Optional pricing (free or paid via Stripe)
 - Download limits
 - Expiration settings

From the user's prompt, you can infer what they want to share and how they want to configure it.

## Pricing
File shares can be free or paid:
 - Free shares: no cost to download
 - Paid shares: one-time payment via Stripe before accessing the file

## Earnings
When you set a price on file shares, payments are processed via Stripe with a 5% platform fee.
You can track your earnings and manage payouts from the Earnings section.`

const routerSystemPrompt = `
${sharedSystemPrompt}

# Your task
Your task is to determine whether the user request requires manual setup, follow-up questions, and if the subsequent LLM call
will require MCP tool access to act on the users request.

At the very least, we need to know what files the user wants to share and whether they want to set a price.
As long as these data points are not clear, follow-up questions will be needed.

If you notice any frustration with the assistant from the user, immediately opt for manual setup.

You will now be handed the last three user messages from the conversation, separated by "---", oldest message first.

Always respond in JSON format with the JSON object ONLY and do not include any extra text.
Do not return Markdown formatting or code fences.
`

const conversationalSystemPrompt = `
${sharedSystemPrompt}

# Share Configuration

File shares can be configured with optional pricing.

In general, you should follow this order:

 - Understand what the user wants to share
 - Define pricing if applicable
 - Create the share with appropriate settings

# Rules
- Never render ID's in your text response.
- Prefer no formatting in your response, but if you do, use valid Markdown (limited to bold, italic, and lists. No headings.)
- Prices will always be in USD. If you are prompted about a different currency, mention that this is not supported yet,
  and ask them to specify their prices in USD. If no currency is mentioned, assume USD. Never ask to confirm the currency,
  nor mention this limitation proactively. Use only a dollar sign ($), no need to repeat USD.
- The share name is not that important, and can be renamed, so keep it simple and descriptive.
- You are capable of creating multiple shares at the same time, so you should hold all of them in context.
- Derive the configuration from what the user has told you, don't propose setups they didn't ask for.
- The goal is to get the user to a minimal configuration fast, so once there is reasonable confidence that you have all the information you need,
  do not ask for more information. Users will always be able to adjust settings later.
- If the request is not relevant to file sharing, gently decline the request and mention that you're only able to help with file sharing.
- Be eager to resolve the request as quickly as possible.
- If you use the "renderSharesPreview" tool, do not repeat the preview in the text response after that.
- Be friendly and helpful if people ask questions like "What is Rapidly?" or "How does file sharing work?".

The user will now describe what they want to share and you will help them set it up.
`

// ── OAuth Token Generation ──

async function generateOAT(
  userId: string,
  workspaceId: string,
): Promise<string> {
  const requestCookies = await cookies()

  const mcpCookie = requestCookies.get(CONFIG.AUTH_MCP_COOKIE_KEY)
  if (mcpCookie) {
    return mcpCookie.value
  }

  const userSessionToken = requestCookies.get(CONFIG.AUTH_COOKIE_KEY)
  if (!userSessionToken) {
    throw new Error('No user session cookie found')
  }

  const client = await getServerSideAPI()
  const { data, error } = await client.POST('/api/oauth2/token', {
    body: {
      grant_type: 'web',
      client_id: process.env.MCP_OAUTH2_CLIENT_ID!,
      client_secret: process.env.MCP_OAUTH2_CLIENT_SECRET!,
      session_token: userSessionToken.value,
      sub_type: 'workspace',
      sub: workspaceId,
      scope: null,
    },
    bodySerializer(body) {
      const fd = new FormData()
      for (const [key, value] of Object.entries(body)) {
        if (value) {
          fd.append(key, value)
        }
      }
      return fd
    },
  })

  if (error) {
    throw new Error('Failed to generate OAT')
  }

  const accessToken = data.access_token

  if (!accessToken) {
    throw new Error('Failed to generate OAT')
  }

  requestCookies.set(CONFIG.AUTH_MCP_COOKIE_KEY, accessToken, {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    expires: new Date(Date.now() + data.expires_in * 1000),
  })

  return accessToken
}

// ── MCP Client ──

async function getMCPClient(userId: string, workspaceId: string) {
  const oat = await generateOAT(userId, workspaceId)

  const httpTransport = new StreamableHTTPClientTransport(
    new URL('https://app.getgram.ai/mcp/rapidly-onboarding-assistant'),
    {
      requestInit: {
        headers: {
          Authorization: `Bearer ${process.env.GRAM_API_KEY}`,
          'MCP-RAPIDLY-SERVER-URL':
            process.env.GRAM_API_URL ?? process.env.NEXT_PUBLIC_API_URL!,
          'MCP-RAPIDLY-ACCESS-TOKEN': oat,
        },
      },
    },
  )

  const mcpClient = await experimental_createMCPClient({
    transport: httpTransport,
  })

  return mcpClient
}

// ── Route Handler ──

export async function POST(req: Request) {
  const user = await getAuthenticatedUser()
  if (!user) {
    return new Response('Unauthorized', { status: 401 })
  }

  const {
    messages,
    workspaceId,
    conversationId,
  }: { messages: UIMessage[]; workspaceId: string; conversationId: string } =
    await req.json()

  const hasToolAccess = (await cookies()).has(CONFIG.AUTH_MCP_COOKIE_KEY)
  let requiresToolAccess = false
  let requiresManualSetup = false
  let isRelevant = true // assume good faith
  let requiresClarification = true

  if (!workspaceId) {
    return new Response('Workspace ID is required', { status: 400 })
  }

  let tools = {}

  const lastUserMessages = messages.filter((m) => m.role === 'user').reverse()

  if (lastUserMessages.length === 0) {
    return new Response('No user message found', { status: 400 })
  }

  const userMessage = lastUserMessages
    .slice(0, 5)
    .reverse()
    .map((m) =>
      m.parts
        .filter((part) => part.type === 'text')
        .map((part) => part.text)
        .join(' '),
    )
    .join('\n---\n')

  // ── Model Configuration ──

  const geminiLite = phClient
    ? withTracing(google('gemini-2.5-flash-lite'), phClient, {
        posthogDistinctId: user.id,
        posthogTraceId: conversationId,
        posthogGroups: { workspace: workspaceId },
      })
    : google('gemini-2.5-flash-lite')

  const gemini = phClient
    ? withTracing(google('gemini-2.5-flash'), phClient, {
        posthogDistinctId: user.id,
        posthogTraceId: conversationId,
        posthogGroups: { workspace: workspaceId },
      })
    : google('gemini-2.5-flash')

  const sonnet = phClient
    ? withTracing(anthropic('claude-sonnet-4-5'), phClient, {
        posthogDistinctId: user.id,
        posthogTraceId: conversationId,
        posthogGroups: { workspace: workspaceId },
      })
    : anthropic('claude-sonnet-4-5')

  // ── Intent Router ──

  const router = await generateObject({
    model: geminiLite,
    output: 'object',
    schema: z.object({
      isRelevant: z
        .boolean()
        .describe(
          'Whether the user request is relevant to configuring their Rapidly account',
        ),
      requiresManualSetup: z
        .boolean()
        .describe(
          'Whether the user request requires manual setup due to too complex configuration',
        ),
      requiresToolAccess: z
        .boolean()
        .describe(
          'Whether MCP access is required to act on the user request (get, create, update, delete shares)',
        ),
      requiresClarification: z
        .boolean()
        .describe(
          'Whether there is enough information to act on the user request or if we need further clarification',
        ),
    }),
    system: routerSystemPrompt,
    prompt: userMessage,
  })

  if (!router.object.isRelevant) {
    isRelevant = false
  } else {
    requiresManualSetup = router.object.requiresManualSetup
    requiresToolAccess = router.object.requiresToolAccess
    requiresClarification = router.object.requiresClarification
  }

  let shouldSetupTools = false

  // If we'll be handling the request agentically
  if (isRelevant && !requiresManualSetup && requiresToolAccess) {
    if (!requiresClarification) {
      // We have enough info to act right away, set up tools
      shouldSetupTools = true
    } else if (lastUserMessages.length >= 5 && hasToolAccess) {
      // Conversation has been going on for a while and we had tool access before
      shouldSetupTools = true
    }
  }

  if (shouldSetupTools) {
    const mcpClient = await getMCPClient(user.id, workspaceId)
    tools = await mcpClient.tools()
  }

  // ── Tool Definitions ──

  const redirectToManualSetup = tool({
    description: 'Request the user to manually configure the share instead',
    inputSchema: z.object({
      reason: z
        .enum(['tool_call_error', 'user_requested'])
        .describe(
          'The reason why the user should manually configure the share',
        ),
    }),
  })

  const markAsDone = tool({
    description: `Mark the onboarding as done call, this tool once shares have been fully created.

You can call this tool only once as it will end the onboarding flow, so make sure your work is done.
However, don't specifically ask if the user wants anything else before calling this tool. Use your own judgement
based on the conversation history whether you're done.

`,
    inputSchema: z.object({
      shareIds: z.array(z.string()).describe('The UUIDs of the created shares'),
    }),
    execute: async ({ shareIds }) => {
      const api = await getServerSideAPI()
      await api.POST('/api/workspaces/{id}/ai-onboarding-complete', {
        params: { path: { id: workspaceId } },
      })
      return { success: true, shareIds }
    },
  })

  // ── Stream Response ──

  let streamStarted = false

  const result = streamText({
    // Gemini 2.5 Flash for quick & cheap responses, Sonnet 4.5 for better tool usage
    model: shouldSetupTools ? sonnet : gemini,
    tools: {
      redirectToManualSetup,
      ...(!requiresManualSetup ? { markAsDone } : {}), // only allow done if we can actually create shares
      ...tools,
    },
    toolChoice: requiresManualSetup
      ? { type: 'tool', toolName: 'redirectToManualSetup' }
      : 'auto',
    messages: [
      {
        role: 'system',
        content: conversationalSystemPrompt,
        providerOptions: shouldSetupTools
          ? {
              anthropic: {
                cacheControl: { type: 'ephemeral' },
              },
            }
          : {},
      },
      ...convertToModelMessages(messages),
    ],
    stopWhen: stepCountIs(15),
    experimental_transform: smoothStream(),
    onChunk: () => {
      if (!streamStarted) {
        streamStarted = true
      }
    },
    onFinish: () => {
      if (phClient) {
        phClient.flush()
      }
    },
  })

  return result.toUIMessageStreamResponse()
}
