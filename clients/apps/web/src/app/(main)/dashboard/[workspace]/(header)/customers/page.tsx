import { redirect } from 'next/navigation'

/** Customers page redirecting to the files view for the workspace. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  redirect(`/dashboard/${params.workspace}/files`)
}
