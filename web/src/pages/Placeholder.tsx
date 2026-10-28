import { Link } from "react-router-dom";

import { Icon } from "../components/ui/Icon";

interface PlaceholderProps {
  title: string;
  description: string;
}

export default function Placeholder({ title, description }: PlaceholderProps) {
  return (
    <div className="mx-auto max-w-xl py-16 text-center">
      <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-500">
        <Icon name="spark" />
      </div>
      <h1 className="mt-5 text-xl font-semibold">{title}</h1>
      <p className="mt-2 text-sm leading-6 text-zinc-500">{description}</p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-brand-500 px-4 py-2 text-sm font-medium text-ink-950 transition hover:bg-brand-400"
      >
        返回首页
        <Icon name="arrowRight" className="size-4" />
      </Link>
    </div>
  );
}
