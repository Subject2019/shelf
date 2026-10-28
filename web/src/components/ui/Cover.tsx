import { coverGradient, initialOf } from "../../lib/format";
import { useCoverUrl, type CoverSize } from "../../lib/cover";

interface CoverProps {
  book: { id: number; title: string; cover_url?: string | null };
  /** thumb 用于列表与播放条，full 用于详情与大封面。 */
  size?: CoverSize;
  /** 尺寸与圆角由调用方决定，这里只负责填满。 */
  className?: string;
  textClassName?: string;
}

/** 有图用图，没图用书名哈希生成的渐变 + 首字，两者尺寸完全一致。 */
export default function Cover({
  book,
  size = "thumb",
  className = "",
  textClassName = "text-4xl",
}: CoverProps) {
  // 系列文件夹是「伪书」（id=0），封面 URL 指向组内第一本书；
  // 直接按 id 请求会打到 /books/0/cover 得 404，所以从 URL 里取真实 id。
  const fromUrl = book.cover_url?.match(/\/books\/(\d+)\/cover/);
  const coverId = fromUrl ? Number(fromUrl[1]) : book.id;
  const url = useCoverUrl(coverId, size, Boolean(book.cover_url));

  if (url) {
    return (
      <img
        src={url}
        alt=""
        aria-hidden="true"
        className={`${className} object-cover`}
      />
    );
  }

  return (
    <div
      className={`${className} flex items-center justify-center font-semibold text-white/85`}
      style={{ background: coverGradient(book.title) }}
    >
      <span className={textClassName}>{initialOf(book.title)}</span>
    </div>
  );
}
