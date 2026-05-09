export interface SearchResultBase {
  id: string
  type: string
}

export interface SearchResultShare extends SearchResultBase {
  type: 'share'
  name: string
  description?: string | null
}

export interface SearchResultCustomer extends SearchResultBase {
  type: 'customer'
  name: string | null
  email: string
}

export interface SearchResultPage extends SearchResultBase {
  type: 'page'
  title: string
  url: string
  icon?: React.ReactNode
}

export interface SearchResultAction extends SearchResultBase {
  type: 'action'
  title: string
  url: string
  icon?: React.ReactNode
}

export type SearchResult =
  | SearchResultShare
  | SearchResultCustomer
  | SearchResultPage
  | SearchResultAction
