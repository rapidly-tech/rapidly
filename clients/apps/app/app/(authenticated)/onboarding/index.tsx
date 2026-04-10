import { FormInput } from '@/components/Form/FormInput'
import { Box } from '@/components/Shared/Box'
import { Button } from '@/components/Shared/Button'
import { Checkbox } from '@/components/Shared/Checkbox'
import { Text } from '@/components/Shared/Text'
import { Touchable } from '@/components/Shared/Touchable'
import { useTheme } from '@/design-system/useTheme'
import { useCreateWorkspace } from '@/hooks/rapidly/workspaces'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { queryClient } from '@/utils/query'
import { ApiResponseError, schemas } from '@rapidly-tech/client'
import { Stack, useRouter } from 'expo-router'
import { useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Linking, SafeAreaView, ScrollView } from 'react-native'
import slugify from 'slugify'

export default function Onboarding() {
  const theme = useTheme()
  const router = useRouter()
  const { workspaces, setWorkspace } = useContext(WorkspaceContext)

  const form = useForm<schemas['WorkspaceCreate'] & { terms: boolean }>({
    defaultValues: {
      name: '',
      slug: '',
      terms: false,
    },
  })

  const {
    control,
    handleSubmit,
    watch,
    setError,
    clearErrors,
    setValue,
    formState: { errors },
  } = form

  const createWorkspace = useCreateWorkspace()
  const [editedSlug, setEditedSlug] = useState(false)

  const name = watch('name')
  const slug = watch('slug')
  const terms = watch('terms')

  const isValid = useMemo(() => {
    return name.length > 2 && slug.length > 2 && terms
  }, [name, slug, terms])

  useEffect(() => {
    if (!editedSlug && name) {
      setValue('slug', slugify(name, { lower: true, strict: true }))
    } else if (slug) {
      setValue(
        'slug',
        slugify(slug, { lower: true, trim: false, strict: true }),
      )
    }
  }, [name, editedSlug, slug, setValue])

  const onSubmit = useCallback(
    async (data: schemas['WorkspaceCreate']) => {
      clearErrors('root')
      try {
        const workspace = await createWorkspace.mutateAsync(data)
        setWorkspace(workspace)
        await queryClient.refetchQueries({ queryKey: ['workspaces'] })
        router.replace('/')
      } catch (error) {
        if (error instanceof ApiResponseError) {
          const errorDetail = error.error.detail

          if (Array.isArray(errorDetail)) {
            const validationError = errorDetail[0]

            setError('root', { message: validationError.msg })
            return
          }
        }

        setError('root', {
          message:
            error instanceof Error
              ? error.message
              : 'Failed to create workspace',
        })
      }
    },
    [clearErrors, createWorkspace, setWorkspace, router, setError],
  )

  return (
    <ScrollView
      contentContainerStyle={{
        backgroundColor: theme.colors.background,
        paddingBottom: theme.spacing['spacing-16'],
      }}
    >
      <Stack.Screen
        options={{
          header: () => null,
        }}
      />
      <SafeAreaView
        style={{
          margin: theme.spacing['spacing-16'],
          gap: theme.spacing['spacing-32'],
        }}
      >
        <Box gap="spacing-16">
          <Text
            variant="display"
            style={{
              paddingVertical: theme.spacing['spacing-32'],
            }}
          >
            Create your workspace
          </Text>
          {errors.root ? (
            <Text color="error">{errors.root.message}</Text>
          ) : null}
          <FormInput
            label="Workspace Name"
            placeholder="Acme Inc."
            control={control}
            name="name"
          />
          <FormInput
            label="Workspace Slug"
            placeholder="acme-inc"
            control={control}
            onFocus={() => setEditedSlug(true)}
            name="slug"
          />
          <Checkbox
            label="I agree to the terms below"
            checked={watch('terms')}
            onChange={(checked) => setValue('terms', checked)}
          />
          <Box>
            <Box marginLeft="spacing-4" gap="spacing-8">
              <Box flexDirection="row" alignItems="flex-start">
                <Box>
                  <Touchable
                    onPress={() =>
                      Linking.openURL(
                        'https://docs.rapidly.tech/acceptable-use',
                      )
                    }
                  >
                    <Text color="primary">Acceptable Use Policy</Text>
                  </Touchable>
                  <Text color="subtext">
                    I&apos;ll only sell digital products and SaaS that complies
                    with it or risk suspension.
                  </Text>
                </Box>
              </Box>
              <Box>
                <Touchable
                  onPress={() =>
                    Linking.openURL('https://docs.rapidly.tech/account-reviews')
                  }
                >
                  <Text color="primary">Account Reviews</Text>
                </Touchable>
                <Text color="subtext">
                  I&apos;ll comply with all reviews and requests for compliance
                  materials (KYC/AML).
                </Text>
              </Box>
              <Box>
                <Touchable
                  onPress={() =>
                    Linking.openURL('https://rapidly.tech/legal/terms')
                  }
                >
                  <Text color="primary">Terms of Service</Text>
                </Touchable>
              </Box>

              <Box>
                <Touchable
                  onPress={() =>
                    Linking.openURL('https://rapidly.tech/legal/privacy')
                  }
                >
                  <Text color="primary">Privacy Policy</Text>
                </Touchable>
              </Box>
            </Box>
          </Box>
        </Box>

        <Box gap="spacing-8">
          <Box>
            <Button onPress={handleSubmit(onSubmit)} disabled={!isValid}>
              Create Workspace
            </Button>
          </Box>
          {workspaces.length > 0 ? (
            <Box>
              <Button onPress={() => router.replace('/')} variant="secondary">
                Back to Dashboard
              </Button>
            </Box>
          ) : null}
        </Box>
      </SafeAreaView>
    </ScrollView>
  )
}
