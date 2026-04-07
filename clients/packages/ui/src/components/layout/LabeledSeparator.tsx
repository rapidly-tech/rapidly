interface LabeledSeparatorProps {
  label: string
}

const LabeledSeparator: React.FC<LabeledSeparatorProps> = ({ label }) => {
  return (
    <div className="flex w-full flex-row items-center gap-6">
      <div className="grow border-t border-slate-200 dark:border-slate-700"></div>
      <div className="text-sm text-slate-500 dark:text-slate-400">{label}</div>
      <div className="grow border-t border-slate-200 dark:border-slate-700"></div>
    </div>
  )
}

export default LabeledSeparator
