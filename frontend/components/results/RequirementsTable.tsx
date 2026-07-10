"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { ListFilter, MessageCircleQuestion, Search } from "lucide-react";
import { FLAG_COLORS, LAYER_COLORS, PRIORITY_COLORS } from "@/lib/badges";
import type { AEPLayer, Requirement } from "@/lib/types";
import { cn } from "@/lib/utils";

const ALL_LAYERS: AEPLayer[] = ["schema", "dataset", "ingestion", "modeling", "activation", "governance", "reporting", "general"];

export function RequirementsTable({
  requirements,
  onSelect,
  onAskAbout,
  highlightReqId,
  onHighlightConsumed,
}: {
  requirements: Requirement[];
  onSelect?: (req: Requirement) => void;
  onAskAbout?: (question: string) => void;
  highlightReqId?: string | null;
  onHighlightConsumed?: () => void;
}) {
  const [search, setSearch] = useState("");
  const [layerFilter, setLayerFilter] = useState<Set<AEPLayer>>(new Set());
  const rowRefs = useRef<Map<string, HTMLTableRowElement>>(new Map());

  useEffect(() => {
    if (!highlightReqId) return;
    // Clear any filters that would hide the target row.
    setSearch("");
    setLayerFilter(new Set());
    const timer = setTimeout(() => {
      rowRefs.current.get(highlightReqId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    const clearTimer = setTimeout(() => onHighlightConsumed?.(), 2200);
    return () => {
      clearTimeout(timer);
      clearTimeout(clearTimer);
    };
  }, [highlightReqId, onHighlightConsumed]);

  const filtered = useMemo(() => {
    return requirements.filter((r) => {
      if (layerFilter.size > 0 && !layerFilter.has(r.aep_layer)) return false;
      if (search && !r.description.toLowerCase().includes(search.toLowerCase()) && !r.req_id.toLowerCase().includes(search.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [requirements, search, layerFilter]);

  function toggleLayer(layer: AEPLayer) {
    setLayerFilter((prev) => {
      const next = new Set(prev);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return next;
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search requirements..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
            <ListFilter className="mr-1.5 h-4 w-4" />
            Layer {layerFilter.size > 0 && `(${layerFilter.size})`}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {ALL_LAYERS.map((layer) => (
              <DropdownMenuCheckboxItem key={layer} checked={layerFilter.has(layer)} onCheckedChange={() => toggleLayer(layer)}>
                {layer}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <span className="text-sm text-muted-foreground">{filtered.length} of {requirements.length}</span>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">ID</TableHead>
              <TableHead className="w-28">Layer</TableHead>
              <TableHead className="w-20">Priority</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="w-40">Section</TableHead>
              <TableHead className="w-32">Flags</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((r) => (
              <TableRow
                key={r.req_id}
                ref={(el) => {
                  if (el) rowRefs.current.set(r.req_id, el);
                  else rowRefs.current.delete(r.req_id);
                }}
                className={cn(
                  "group cursor-pointer transition-colors",
                  highlightReqId === r.req_id && "bg-brand-accent/15 hover:bg-brand-accent/15"
                )}
                onClick={() => onSelect?.(r)}
              >
                <TableCell className="font-mono text-xs">{r.req_id}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className={cn("font-normal", LAYER_COLORS[r.aep_layer])}>
                    {r.aep_layer}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary" className={cn("font-normal", PRIORITY_COLORS[r.priority])}>
                    {r.priority}
                  </Badge>
                </TableCell>
                <TableCell className="max-w-md whitespace-normal text-sm">{r.description}</TableCell>
                <TableCell className="max-w-40 truncate text-xs text-muted-foreground">{r.source_section}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {r.flags.map((f) => (
                      <Badge key={f} variant="secondary" className={cn("font-normal text-[10px]", FLAG_COLORS[f])}>
                        {f}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAskAbout?.(`Explain requirement ${r.req_id} ("${r.description}") and show me its exact source in the document.`);
                    }}
                  >
                    <MessageCircleQuestion className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
