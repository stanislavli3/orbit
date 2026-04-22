import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  FileText,
  Ruler,
  Layers,
  Palette,
  Sparkles,
} from 'lucide-react';
import { useApiClient } from '../../api/client';
import type { ExtractionResult, UploadedFile } from '../../api/types';
import { PartPreview3D } from './PartPreview3D';

const PAPER = {
  base:      '#F3E7CE',
  highlight: '#F8F0DC',
  fold:      '#E8D6AC',
  ink:       '#2B2824',
  inkSoft:   '#6B5A3F',
  inkFaded:  '#8B7F73',
  stamp:     '#C66A4E',
};

function Squiggle({ color = PAPER.stamp, width = 140 }: { color?: string; width?: number }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 220 12"
      className="-rotate-[0.5deg] block"
      style={{ width, height: 9 }}
      fill="none"
      preserveAspectRatio="none"
    >
      <path
        d="M2 7 Q 22 2, 44 6 T 88 5 Q 112 9, 136 4 T 180 6 Q 200 3, 218 7"
        stroke={color}
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StatRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex items-baseline justify-between py-1.5 border-b border-dashed"
      style={{ borderColor: 'rgba(107, 90, 63, 0.18)' }}
    >
      <span className="text-[11px] uppercase tracking-[0.14em] font-display" style={{ color: PAPER.inkFaded }}>{label}</span>
      <span className="text-[12px] font-mono tabular-nums text-right" style={{ color: PAPER.ink }}>{value}</span>
    </div>
  );
}

function SectionCard({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-[10px] p-4 relative"
      style={{
        background: '#FFFCF7',
        border: `1px solid ${PAPER.fold}`,
        boxShadow: '0 1px 0 rgba(61, 47, 31, 0.03), 0 2px 8px rgba(61, 47, 31, 0.05)',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4" style={{ color: PAPER.stamp }} strokeWidth={1.5} />
        <h3 className="font-display text-[14px] font-medium" style={{ color: PAPER.ink }}>{title}</h3>
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

export function FileResultPage() {
  const { id, fileId } = useParams<{ id: string; fileId: string }>();
  const apiFetch = useApiClient();

  const { data: result, isLoading, error } = useQuery<ExtractionResult>({
    queryKey: ['extraction-result', fileId],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/${fileId}/result/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!fileId,
    retry: false,
  });

  const { data: files } = useQuery<UploadedFile[]>({
    queryKey: ['files', id],
    queryFn: async () => {
      const res = await apiFetch(`/api/files/project/${id}/`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!id,
  });

  const file = files?.find((f) => String(f.id) === fileId) ?? null;

  const bbox = result?.spatial?.bounding_box_estimate;
  const geom = result?.geometry;
  const prods = result?.products;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden" style={{ background: PAPER.base }}>
      {/* Header */}
      <div
        className="flex-shrink-0 relative"
        style={{
          background: PAPER.highlight,
          borderBottom: `1px solid ${PAPER.fold}`,
        }}
      >
        <div className="max-w-[1400px] mx-auto px-8 py-5 flex items-center gap-3">
          <Link
            to={`/project/${id}`}
            className="w-9 h-9 rounded-lg flex items-center justify-center transition-colors"
            style={{ background: '#FFFCF7', border: `1px solid ${PAPER.fold}` }}
          >
            <ArrowLeft className="w-4 h-4" strokeWidth={1.5} style={{ color: PAPER.inkSoft }} />
          </Link>
          <div>
            <p className="text-[10px] font-display uppercase tracking-[0.22em]" style={{ color: PAPER.stamp }}>
              Drawing
            </p>
            <h1 className="font-display text-[24px] leading-[1.15] font-medium tracking-tight" style={{ color: PAPER.ink }}>
              {file?.original_name ?? `File №${fileId}`}
            </h1>
            <div className="mt-0.5">
              <Squiggle />
            </div>
            {file?.file_type && (
              <p className="text-[11px] font-mono mt-1" style={{ color: PAPER.inkFaded }}>
                {file.file_type.toUpperCase()}
                {' · '}
                {file.status}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-[1400px] mx-auto px-8 py-8">
          {isLoading && (
            <div className="flex items-center justify-center py-24 gap-2">
              <Loader2 className="w-4 h-4 animate-spin" style={{ color: PAPER.inkSoft }} />
              <span className="text-sm" style={{ color: PAPER.inkSoft }}>Loading extraction result…</span>
            </div>
          )}

          {error && (
            <div
              className="rounded-[10px] p-4 flex items-start gap-3"
              style={{ background: 'rgba(182, 63, 42, 0.08)', border: `1.5px solid ${PAPER.stamp}` }}
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: PAPER.stamp }} />
              <div>
                <p className="font-display text-[14px] font-medium" style={{ color: PAPER.ink }}>
                  Extraction result not available
                </p>
                <p className="text-[12px] italic mt-0.5" style={{ color: PAPER.inkSoft }}>
                  This file hasn't been processed yet, or the result was lost.
                </p>
              </div>
            </div>
          )}

          {result && (
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
              {/* 3D preview — spans 3 cols on large screens */}
              <div className="lg:col-span-3">
                <PartPreview3D result={result} className="h-[480px]" />
                {result.file_description && (
                  <p className="mt-3 text-[12px] italic" style={{ color: PAPER.inkSoft }}>
                    {result.file_description}
                  </p>
                )}
              </div>

              {/* Metadata side panel */}
              <div className="lg:col-span-2 space-y-4">
                {/* Provenance */}
                <SectionCard icon={FileText} title="Provenance">
                  {result.source_file && <StatRow label="Source file" value={result.source_file} />}
                  {result.schema && <StatRow label="Schema" value={result.schema} />}
                  {result.authoring_system && <StatRow label="Authoring" value={result.authoring_system} />}
                  {result.units?.length_unit && <StatRow label="Units" value={result.units.length_unit} />}
                  <StatRow
                    label="Confidence"
                    value={
                      <span style={{
                        color:
                          result.confidence >= 0.85 ? '#5E7E52'
                          : result.confidence >= 0.6 ? '#C28A3C'
                          : PAPER.stamp,
                      }}>
                        {result.confidence.toFixed(2)}
                      </span>
                    }
                  />
                </SectionCard>

                {/* Dimensions */}
                {bbox && (
                  <SectionCard icon={Ruler} title="Dimensions">
                    <StatRow label="Bounding X" value={`${bbox.x.toFixed(2)} ${result.units?.length_unit ?? ''}`} />
                    <StatRow label="Bounding Y" value={`${bbox.y.toFixed(2)} ${result.units?.length_unit ?? ''}`} />
                    <StatRow label="Bounding Z" value={`${bbox.z.toFixed(2)} ${result.units?.length_unit ?? ''}`} />
                    {result.spatial?.coordinate_point_count != null && (
                      <StatRow label="Coord points" value={result.spatial.coordinate_point_count.toLocaleString()} />
                    )}
                  </SectionCard>
                )}

                {/* Geometry */}
                {geom && (
                  <SectionCard icon={Layers} title="Geometry">
                    {geom.solid_bodies != null && <StatRow label="Solid bodies" value={geom.solid_bodies} />}
                    {geom.faces != null && <StatRow label="Faces" value={geom.faces} />}
                    {geom.edges != null && <StatRow label="Edges" value={geom.edges} />}
                    {geom.vertices != null && <StatRow label="Vertices" value={geom.vertices} />}
                    {geom.circles != null && geom.circles > 0 && <StatRow label="Circles" value={geom.circles} />}
                    {geom.lines != null && geom.lines > 0 && <StatRow label="Lines" value={geom.lines} />}
                  </SectionCard>
                )}

                {/* Products */}
                {prods?.product_names && prods.product_names.length > 0 && (
                  <SectionCard icon={Sparkles} title="Products">
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {prods.product_names.map((name) => (
                        <span
                          key={name}
                          className="px-2 py-0.5 text-[11px] rounded-[3px] font-display"
                          style={{ color: PAPER.ink, background: PAPER.base, border: `1px solid ${PAPER.fold}` }}
                        >
                          {name}
                        </span>
                      ))}
                    </div>
                  </SectionCard>
                )}

                {/* Appearance */}
                {result.appearance?.colours_rgb && result.appearance.colours_rgb.length > 0 && (
                  <SectionCard icon={Palette} title="Colours">
                    <div className="flex flex-wrap gap-2 mt-1">
                      {result.appearance.colours_rgb.slice(0, 8).map((c, i) => (
                        <div
                          key={i}
                          className="w-7 h-7 rounded-[4px]"
                          style={{
                            background: `rgb(${Math.round(c.r * 255)}, ${Math.round(c.g * 255)}, ${Math.round(c.b * 255)})`,
                            border: `1px solid ${PAPER.fold}`,
                          }}
                          title={`rgb(${c.r.toFixed(2)}, ${c.g.toFixed(2)}, ${c.b.toFixed(2)})`}
                        />
                      ))}
                    </div>
                  </SectionCard>
                )}

                {/* Warnings */}
                {result.warnings && result.warnings.length > 0 && (
                  <SectionCard icon={AlertCircle} title="Warnings">
                    <ul className="space-y-1 mt-1">
                      {result.warnings.map((w, i) => (
                        <li key={i} className="text-[11px] italic" style={{ color: PAPER.inkSoft }}>
                          · {w}
                        </li>
                      ))}
                    </ul>
                  </SectionCard>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
