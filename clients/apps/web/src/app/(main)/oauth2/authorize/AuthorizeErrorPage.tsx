import Alert from '@rapidly-tech/ui/components/feedback/Alert'
import Button from '@rapidly-tech/ui/components/forms/Button'
import SharedLayout from './components/SharedLayout'

interface ErrorPageProps {
  error: string
  error_description?: string
  error_uri?: string
}

const ErrorDetails = ({
  message,
  learnMoreUrl,
}: {
  message: string
  learnMoreUrl?: string
}) => (
  <div className="flex flex-col items-center gap-2 p-2 text-center">
    <div className="text-base font-medium">An error occurred</div>
    <div className="text-sm">{message}</div>
    {learnMoreUrl && (
      <a href={learnMoreUrl}>
        <Button variant="default">Read more</Button>
      </a>
    )}
  </div>
)

const AuthorizeErrorPage = ({
  error,
  error_description,
  error_uri,
}: ErrorPageProps) => {
  const displayMessage = error_description ?? error

  return (
    <SharedLayout>
      <Alert color="red">
        <ErrorDetails message={displayMessage} learnMoreUrl={error_uri} />
      </Alert>
    </SharedLayout>
  )
}

export default AuthorizeErrorPage
