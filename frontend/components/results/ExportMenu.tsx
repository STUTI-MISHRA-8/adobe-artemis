"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { exportUrl } from "@/lib/api";

export function ExportMenu({ jobId }: { jobId: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
        <Download className="mr-1.5 h-4 w-4" />
        Export
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem render={<a href={exportUrl(jobId, "requirements_csv")} download />}>
          Requirements (CSV)
        </DropdownMenuItem>
        <DropdownMenuItem render={<a href={exportUrl(jobId, "tasks_csv")} download />}>
          Execution plan (CSV)
        </DropdownMenuItem>
        <DropdownMenuItem render={<a href={exportUrl(jobId, "markdown")} download />}>
          Traceability report (Markdown)
        </DropdownMenuItem>
        <DropdownMenuItem render={<a href={exportUrl(jobId, "json")} download />}>
          Full result (JSON)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
