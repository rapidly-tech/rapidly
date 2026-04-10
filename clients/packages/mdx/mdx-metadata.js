/**
 * Rapidly MDX frontmatter metadata plugin.
 *
 * A remark plugin that parses YAML/TOML frontmatter from MDX files and
 * exposes it as a named export. Also generates OpenGraph image metadata
 * for the Rapidly documentation and blog pages.
 *
 * @module rapidly/mdx/mdx-metadata
 */
import { name as isIdentifierName } from 'estree-util-is-identifier-name'
import { valueToEstree } from 'estree-util-value-to-estree'
import { parse as parseToml } from 'toml'
import { parse as parseYaml } from 'yaml'

const DEFAULT_EXPORT_NAME = 'metadata'

const OG_IMAGE_WIDTH = 1200
const OG_IMAGE_HEIGHT = 630

const DEFAULT_PARSERS = {
  yaml: parseYaml,
  toml: parseToml,
}

const validateExportName = (exportName) => {
  if (!isIdentifierName(exportName)) {
    throw new Error(
      `Name should be a valid identifier, got: ${JSON.stringify(exportName)}`,
    )
  }
}

const buildOpenGraphMeta = (ogImageUrl, frontmatter) => {
  const baseMeta = { type: 'website' }

  if (!ogImageUrl) return baseMeta

  const queryString = new URLSearchParams(frontmatter).toString()
  return {
    ...baseMeta,
    images: [
      {
        url: `${ogImageUrl}?${queryString}`,
        width: OG_IMAGE_WIDTH,
        height: OG_IMAGE_HEIGHT,
      },
    ],
  }
}

const buildExportAstNode = (exportName, exportValue) => ({
  type: 'mdxjsEsm',
  value: '',
  data: {
    estree: {
      type: 'Program',
      sourceType: 'module',
      body: [
        {
          type: 'ExportNamedDeclaration',
          specifiers: [],
          declaration: {
            type: 'VariableDeclaration',
            kind: 'const',
            declarations: [
              {
                type: 'VariableDeclarator',
                id: { type: 'Identifier', name: exportName },
                init: valueToEstree(exportValue, { preserveReferences: true }),
              },
            ],
          },
        },
      ],
    },
  },
})

const findFrontmatterNode = (children, parserMap) =>
  children.find((child) => Object.hasOwn(parserMap, child.type))

const remarkMdxFrontmatter =
  (opengraphImageUrl) =>
  ({ name = DEFAULT_EXPORT_NAME, parsers } = {}) => {
    validateExportName(name)

    const parserMap = { ...DEFAULT_PARSERS, ...parsers }

    return (ast) => {
      let data
      const frontmatterNode = findFrontmatterNode(ast.children, parserMap)

      if (frontmatterNode) {
        const parse = parserMap[frontmatterNode.type]
        data = { ...parse(frontmatterNode.value) }

        const ogMeta = buildOpenGraphMeta(opengraphImageUrl, data)
        data.openGraph = { ...ogMeta, ...data.openGraph }
      }

      ast.children.unshift(buildExportAstNode(name, data))
    }
  }

export default remarkMdxFrontmatter
