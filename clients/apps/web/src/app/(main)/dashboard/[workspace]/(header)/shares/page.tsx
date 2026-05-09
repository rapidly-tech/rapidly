import { redirect } from 'next/navigation'

/** Shares index page that redirects to the send-files sub-route. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  redirect(`/dashboard/${params.workspace}/shares/send-files`)
}
