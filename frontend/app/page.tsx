"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { History, Sparkles } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { DropZone } from "@/components/upload/DropZone";
import { uploadDocument } from "@/lib/api";

export default function Home() {
  const [isUploading, setIsUploading] = useState(false);
  const router = useRouter();

  async function handleFile(file: File) {
    setIsUploading(true);
    try {
      const { job_id } = await uploadDocument(file);
      router.push(`/analyze/${job_id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
      setIsUploading(false);
    }
  }

  return (
    <div className="relative flex flex-1 flex-col items-center justify-center gap-10 px-6 py-24">
      <Link
        href="/history"
        className="absolute top-6 right-6 flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <History className="h-4 w-4" />
        History
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center gap-3 text-center"
      >
        <div className="flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5" />
          Adobe
        </div>
        <h1 className="text-6xl font-bold tracking-[0.08em] sm:text-7xl">ARTEMIS</h1>
        <p className="max-w-xl text-xs font-medium tracking-[0.2em] text-muted-foreground uppercase sm:text-sm">
          AEP Requirement Traceability, Extraction, Mapping &amp; Implementation System
        </p>
        <p className="mt-4 max-w-lg text-balance text-muted-foreground">
          Upload a Business Requirements Document and get structured AEP requirements,
          a phased execution plan, and full traceability back to the source — nothing missed.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <DropZone onFile={handleFile} isUploading={isUploading} />
      </motion.div>
    </div>
  );
}
