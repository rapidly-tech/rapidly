const ItemGroup: React.FC<React.PropsWithChildren> = ({ children }) => (
  <div className="w-full overflow-hidden rounded-2xl border border-slate-200/60 bg-slate-50 shadow-xs lg:rounded-3xl dark:border-slate-700 dark:bg-slate-900">
    {children}
  </div>
)

const ItemGroupRow: React.FC<React.PropsWithChildren> = ({ children }) => (
  <div className="border-t border-slate-200/50 p-5 first:border-t-0 dark:border-slate-700">
    {children}
  </div>
)

export default Object.assign(ItemGroup, {
  Item: ItemGroupRow,
})
