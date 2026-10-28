import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import type { BookDetail, BookUpdatePayload } from "../../api/types";
import { Icon } from "../ui/Icon";

interface MetadataEditorProps {
  book: BookDetail;
  onClose: () => void;
  onSaved: (book: BookDetail) => void;
}

interface FormState {
  title: string;
  subtitle: string;
  author: string;
  narrator: string;
  publisher: string;
  publish_year: string;
  language: string;
  series_name: string;
  series_index: string;
  description: string;
}

function toForm(book: BookDetail): FormState {
  return {
    title: book.title,
    subtitle: book.subtitle ?? "",
    author: book.author ?? "",
    narrator: book.narrator ?? "",
    publisher: book.publisher ?? "",
    publish_year: book.publish_year ? String(book.publish_year) : "",
    language: book.language ?? "",
    series_name: book.series_name ?? "",
    series_index: book.series_index ? String(book.series_index) : "",
    description: book.description ?? "",
  };
}

export default function MetadataEditor({ book, onClose, onSaved }: MetadataEditorProps) {
  const [form, setForm] = useState<FormState>(() => toForm(book));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(toForm(book));
  }, [book]);

  const save = useMutation({
    mutationFn: (payload: BookUpdatePayload) => api.updateBook(book.id, payload),
    onSuccess: () => {
      onSaved({
        ...book,
        title: form.title.trim(),
        subtitle: form.subtitle.trim() || null,
        author: form.author.trim() || null,
        narrator: form.narrator.trim() || null,
        publisher: form.publisher.trim() || null,
        publish_year: form.publish_year ? Number(form.publish_year) : null,
        language: form.language.trim() || null,
        series_name: form.series_name.trim() || null,
        series_index: form.series_index ? Number(form.series_index) : null,
        description: form.description.trim() || null,
        manual_override: true,
      });
      onClose();
    },
    onError: (value) => {
      setError(value instanceof ApiError ? value.message : "保存失败");
    },
  });

  function submit() {
    if (!form.title.trim()) {
      setError("书名不能为空");
      return;
    }
    setError(null);
    save.mutate({
      title: form.title.trim(),
      subtitle: form.subtitle.trim() || null,
      author: form.author.trim() || null,
      narrator: form.narrator.trim() || null,
      publisher: form.publisher.trim() || null,
      publish_year: form.publish_year ? Number(form.publish_year) : null,
      language: form.language.trim() || null,
      series_name: form.series_name.trim() || null,
      series_index: form.series_index ? Number(form.series_index) : null,
      description: form.description.trim() || null,
    });
  }

  const field =
    "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-brand-500 dark:border-white/10 dark:bg-white/[0.06]";

  function bind(name: keyof FormState) {
    return {
      value: form[name],
      onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setForm((current) => ({ ...current, [name]: event.target.value })),
    };
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="关闭"
        onClick={onClose}
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
      />

      <div className="glass-panel relative flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl border border-white/60 shadow-2xl dark:border-white/10 sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-zinc-200/70 px-5 py-3 dark:border-white/5">
          <div>
            <h2 className="text-sm font-semibold">编辑资料</h2>
            <p className="mt-0.5 text-[11px] text-zinc-500">
              保存后会标记为手工修改，重新扫描不会覆盖
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10"
          >
            <Icon name="close" className="size-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div>
            <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-title">
              书名 <span className="text-rose-500">*</span>
            </label>
            <input id="meta-title" className={field} {...bind("title")} />
          </div>

          <div>
            <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-subtitle">
              副标题
            </label>
            <input id="meta-subtitle" className={field} {...bind("subtitle")} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-author">
                作者
              </label>
              <input id="meta-author" className={field} {...bind("author")} />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-narrator">
                演播者
              </label>
              <input
                id="meta-narrator"
                className={field}
                placeholder="如：李野墨"
                {...bind("narrator")}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-publisher">
                出版社 / 平台
              </label>
              <input id="meta-publisher" className={field} {...bind("publisher")} />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-year">
                出版年份
              </label>
              <input
                id="meta-year"
                type="number"
                inputMode="numeric"
                className={field}
                placeholder="2009"
                {...bind("publish_year")}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-series">
                系列
              </label>
              <input id="meta-series" className={field} {...bind("series_name")} />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-index">
                第几部
              </label>
              <input
                id="meta-index"
                type="number"
                step="0.5"
                inputMode="decimal"
                className={field}
                placeholder="1"
                {...bind("series_index")}
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-language">
                语言
              </label>
              <input
                id="meta-language"
                className={field}
                placeholder="zh-CN"
                {...bind("language")}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[11px] text-zinc-500" htmlFor="meta-description">
              简介
            </label>
            <textarea
              id="meta-description"
              rows={6}
              className={`${field} resize-y leading-6`}
              placeholder="内容简介、主播信息、版本说明…"
              {...bind("description")}
            />
          </div>

          {error && (
            <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-500">{error}</p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-zinc-200/70 px-5 py-3 dark:border-white/5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-zinc-600 transition hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-white/10"
          >
            取消
          </button>
          <button
            type="button"
            disabled={save.isPending}
            onClick={submit}
            className="btn-gradient rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
          >
            {save.isPending ? "保存中…" : "保存"}
          </button>
        </footer>
      </div>
    </div>
  );
}
