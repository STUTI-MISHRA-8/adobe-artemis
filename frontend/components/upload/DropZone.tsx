"use client";

import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { FileText, Loader2, UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

interface DropZoneProps {
  onFile: (file: File) => void;
  isUploading: boolean;
}

const ACCEPTED = [".pdf", ".docx"];

export function DropZone({ onFile, isUploading }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  return (
    <motion.label
      htmlFor="doc-upload"
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      whileHover={{ scale: isUploading ? 1 : 1.01 }}
      className={cn(
        "group relative flex w-full max-w-xl cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-16 text-center transition-all duration-300",
        isDragging
          ? "border-primary bg-primary/5 shadow-[0_0_50px_-6px_var(--primary)]"
          : "border-border hover:border-primary/50 hover:bg-muted/40 hover:shadow-[0_0_40px_-12px_var(--primary)]",
        isUploading && "pointer-events-none opacity-70"
      )}
    >
      <input
        id="doc-upload"
        type="file"
        accept={ACCEPTED.join(",")}
        className="hidden"
        onChange={handleSelect}
        disabled={isUploading}
      />
      {isUploading ? (
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      ) : (
        <motion.div
          animate={isDragging ? { y: -4 } : { y: 0 }}
          className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-primary"
        >
          {isDragging ? <FileText className="h-8 w-8" /> : <UploadCloud className="h-8 w-8" />}
        </motion.div>
      )}
      <div>
        <p className="text-base font-medium">
          {isUploading ? "Uploading..." : "Drop a BRD or SDD here, or click to browse"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">PDF or DOCX — analyzed by an AEP solution architect AI</p>
      </div>
    </motion.label>
  );
}
