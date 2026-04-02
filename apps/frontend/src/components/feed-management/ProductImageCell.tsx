"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";

export function ProductImageCell({ src }: { src: unknown }) {
  const [errored, setErrored] = useState(false);
  const url = typeof src === "string" && src ? src : null;

  if (!url || errored) {
    return (
      <div className="flex h-[50px] w-[50px] items-center justify-center rounded bg-slate-100 dark:bg-slate-800">
        <ImageOff className="h-4 w-4 text-slate-400" />
      </div>
    );
  }

  return (
    <img
      src={url}
      alt=""
      loading="lazy"
      onError={() => setErrored(true)}
      className="h-[50px] w-[50px] rounded object-cover"
    />
  );
}
