export async function GET() {
  return new Response(
    `
     ____             _     _ _
    |  _ \\ __ _ _ __ (_) __| | |_   _
    | |_) / _\` | '_ \\| |/ _\` | | | | |
    |  _ < (_| | |_) | | (_| | | |_| |
    |_| \\_\\__,_| .__/|_|\\__,_|_|\\__, |
               |_|              |___/


              Rapidly is made by all of our wonderful contributors.

                         https://rapidly.tech

    `,
    {
      headers: {
        'Cache-Control': 'no-cache',
      },
      status: 200,
    },
  )
}
