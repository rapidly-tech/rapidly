import { getAuthenticatedUser } from '@/utils/user'
import { handleUpload, type HandleUploadBody } from '@vercel/blob/client'
import { NextResponse } from 'next/server'

const ALLOWED_IMAGE_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
] as const

const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json()) as HandleUploadBody

  try {
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (
        _pathname: string,
        /* clientPayload?: string, */
      ) => {
        const user = await getAuthenticatedUser()
        if (!user) {
          throw new Error('Unauthenticated')
        }

        return {
          maximumSizeInBytes: MAX_FILE_SIZE,
          allowedContentTypes: [...ALLOWED_IMAGE_TYPES],
          tokenPayload: JSON.stringify({
            user_id: user.id,
          }),
        }
      },
      onUploadCompleted: async () => {
        // Run any logic after the file upload completed
      },
    })

    return NextResponse.json(jsonResponse)
  } catch (error) {
    return NextResponse.json(
      { error: (error as Error).message },
      { status: 400 },
    )
  }
}
