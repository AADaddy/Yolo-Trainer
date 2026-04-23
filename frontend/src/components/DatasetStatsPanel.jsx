import Tooltip from "./Tooltip";

const conclusionStyles = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  yellow: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-rose-200 bg-rose-50 text-rose-800"
};

// The dashboard stays intentionally compact so a typical desktop view can compare the
// main dataset-quality signals in one screen without depending on a separate warnings panel.
export default function DatasetStatsPanel({ stats, loading, error }) {
  if (loading) {
    return <EmptyPanel>Loading dataset statistics...</EmptyPanel>;
  }

  if (error) {
    return <EmptyPanel>{error}</EmptyPanel>;
  }

  if (!stats) {
    return <EmptyPanel>Select a dataset version to inspect cumulative statistics.</EmptyPanel>;
  }

  const totalImages = numberOrZero(stats.total_images);
  const totalObjects = numberOrZero(stats.total_objects);
  const avgObjectsPerImage = numberOrZero(stats.avg_objects_per_image);
  const classBalance = Array.isArray(stats.class_balance) ? stats.class_balance : [];
  const classCoverage = Array.isArray(stats.class_coverage) ? stats.class_coverage : [];
  const objectsPerImage = Array.isArray(stats.objects_per_image_distribution) ? stats.objects_per_image_distribution : [];
  const bboxDistribution = stats.bounding_box_distribution ?? {};
  const resolutionSummary = stats.resolution_summary ?? {};

  const classBalanceConclusion = summarizeClassBalance(classBalance);
  const classCoverageConclusion = summarizeClassCoverage(classCoverage);
  const objectDensityConclusion = summarizeObjectDensity(objectsPerImage);
  const bboxConclusion = summarizeBoundingBoxes(bboxDistribution);
  const resolutionConclusion = summarizeResolution(resolutionSummary);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          title="Total Images"
          tooltip={{
            title: "Total Images",
            body:
              "Shows the cumulative image pool for the selected version. Read this as overall dataset size: larger is better only if both classes still appear often enough to teach YOLO useful scene variation."
          }}
          value={totalImages}
          conclusion={{ tone: totalImages > 0 ? "green" : "yellow", text: totalImages > 0 ? "Cumulative dataset loaded" : "No accepted images yet" }}
        />
        <StatCard
          title="Total Objects"
          tooltip={{
            title: "Total Objects",
            body:
              "Counts all labeled objects across the cumulative dataset. This helps separate image count from annotation density: more objects usually means richer training signal, while very low counts can limit detector quality."
          }}
          value={totalObjects}
          conclusion={{
            tone: totalObjects > 0 ? "green" : "yellow",
            text: totalObjects > 0 ? "Object annotations available" : "No objects found yet"
          }}
        />
        <StatCard
          title="Avg Objects / Image"
          tooltip={{
            title: "Average Objects Per Image",
            body:
              "Summarizes average scene density. Read it alongside the bucket chart below: very sparse scenes can weaken learning, while overly crowded scenes can make YOLO localization harder."
          }}
          value={avgObjectsPerImage.toFixed(2)}
          conclusion={objectDensityConclusion}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Widget
          title="Class Balance"
          tooltip={{
            title: "Class Balance",
            body:
              "Shows each class share using object count and image count. For a 2-class YOLO dataset, healthier splits are closer together; one class dominating the labels usually biases the model toward that class."
          }}
          conclusion={classBalanceConclusion}
        >
          {classBalance.length ? (
            <div className="space-y-3">
              {classBalance.map((row) => (
                <MetricBar
                  key={row.class_id}
                  label={row.class_name}
                  percentage={numberOrZero(row.percentage)}
                  colorClass="bg-blue-500"
                  meta={`${(numberOrZero(row.percentage) * 100).toFixed(1)}% split`}
                  details={[
                    `${numberOrZero(row.object_count)} objects`,
                    `${numberOrZero(row.image_count)} images`
                  ]}
                />
              ))}
            </div>
          ) : (
            <NoDataMessage>No class balance data yet.</NoDataMessage>
          )}
        </Widget>

        <Widget
          title="Class Coverage"
          tooltip={{
            title: "Class Coverage",
            body:
              "Shows what percentage of images contain each class. A class can have many labels but still appear in too few scenes, which weakens YOLO's ability to generalize to new frames."
          }}
          conclusion={classCoverageConclusion}
        >
          {classCoverage.length ? (
            <div className="space-y-3">
              {classCoverage.map((row) => (
                <MetricBar
                  key={row.class_id}
                  label={row.class_name}
                  percentage={numberOrZero(row.image_ratio)}
                  colorClass="bg-emerald-500"
                  meta={`${(numberOrZero(row.image_ratio) * 100).toFixed(1)}% of images`}
                  details={[`${numberOrZero(row.image_count)} images contain this class`]}
                />
              ))}
            </div>
          ) : (
            <NoDataMessage>No class coverage data yet.</NoDataMessage>
          )}
        </Widget>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Widget
          title="Objects Per Image"
          tooltip={{
            title: "Objects Per Image",
            body:
              "Buckets images by object density: 0, 1-2, 3-5, and more than 5. Healthy datasets usually avoid too many empty scenes or too many crowded scenes because both extremes can hurt YOLO stability."
          }}
          conclusion={objectDensityConclusion}
        >
          {objectsPerImage.length ? (
            <div className="space-y-3">
              {objectsPerImage.map((bucket) => (
                <MetricBar
                  key={bucket.bucket}
                  label={bucket.label}
                  percentage={numberOrZero(bucket.percentage)}
                  colorClass="bg-indigo-500"
                  meta={`${numberOrZero(bucket.count)} images`}
                />
              ))}
            </div>
          ) : (
            <NoDataMessage>No object-density data yet.</NoDataMessage>
          )}
        </Widget>

        <Widget
          title="Box Area"
          tooltip={{
            title: "Normalized Box Area",
            body:
              "Uses normalized YOLO box area, width times height, to compare object scale across different image resolutions. Tiny and small boxes are harder for YOLO, but area alone does not fully capture pixel detail or tall thin people."
          }}
          conclusion={bboxConclusion}
        >
          <BucketBars rows={bboxDistribution.area_distribution} emptyText="No bounding-box area data yet." />
        </Widget>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Widget
          title="Box Height + Visibility"
          tooltip={{
            title: "Height And Pixel Visibility",
            body:
              "Shows normalized box height and source pixel-height visibility. For people, height often reflects usable detail better than area because people are tall and thin. Boxes under 15 px tall are risky, and many boxes under 30 px can make staff/customer classification unreliable after resizing."
          }}
          conclusion={bboxConclusion}
        >
          <BoxHeightVisibilityWidget distribution={bboxDistribution} />
        </Widget>

        <Widget
          title="Resolution Analysis"
          tooltip={{
            title: "Resolution Analysis",
            body:
              "Shows the dominant resolution, top 3 resolution groups, and an Other bucket. Resolution consistency still matters for YOLO because resizing does not fully remove differences in framing, object scale, or padding behavior."
          }}
          conclusion={resolutionConclusion}
        >
          <ResolutionWidget resolutionSummary={resolutionSummary} totalImages={totalImages} />
        </Widget>
      </div>
    </div>
  );
}

function StatCard({ title, tooltip, value, conclusion }) {
  return (
    <Widget title={title} tooltip={tooltip} conclusion={conclusion} compact>
      <div className="flex min-h-16 items-center justify-center text-3xl font-semibold text-slate-900">{value}</div>
    </Widget>
  );
}

function Widget({ title, tooltip, conclusion, children, compact = false }) {
  return (
    <div
      className={`rounded-2xl border border-slate-200 bg-white p-4 shadow-sm ${
        compact ? "min-h-[168px]" : "min-h-[256px]"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        <HelpTooltip title={tooltip.title} body={tooltip.body} />
      </div>
      <div className="mt-3">{children}</div>
      <ConclusionBox conclusion={conclusion} />
    </div>
  );
}

function ConclusionBox({ conclusion }) {
  const tone = conclusion?.tone && conclusionStyles[conclusion.tone] ? conclusion.tone : "yellow";
  const text = conclusion?.text || "No conclusion available.";
  // Health state lives in the conclusion box so the charts stay neutral and easy to compare.
  return (
    <div className={`mt-3 rounded-xl border px-3 py-2 text-sm font-medium ${conclusionStyles[tone]}`}>
      {text}
    </div>
  );
}

function MetricBar({ label, percentage, colorClass = "bg-slate-500", meta, details = [] }) {
  const safePercent = Math.max(0, Math.min(100, numberOrZero(percentage) * 100));
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium text-slate-900">{label}</div>
        <div className="text-xs text-slate-500">{meta}</div>
      </div>
      {!!details.length && (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
          {details.map((detail) => (
            <span key={detail}>{detail}</span>
          ))}
        </div>
      )}
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${safePercent}%` }} />
      </div>
      <div className="mt-2 text-right text-xs text-slate-500">{safePercent.toFixed(1)}%</div>
    </div>
  );
}

function BucketBars({ rows, emptyText }) {
  const safeRows = Array.isArray(rows) ? rows : [];
  if (!safeRows.length) {
    return <NoDataMessage>{emptyText}</NoDataMessage>;
  }
  return (
    <div className="space-y-3">
      {safeRows.map((row) => (
        <MetricBar
          key={row.bucket}
          label={row.label}
          percentage={numberOrZero(row.percentage)}
          colorClass="bg-slate-500"
          meta={`${numberOrZero(row.count)} boxes`}
          details={[row.range].filter(Boolean)}
        />
      ))}
    </div>
  );
}

function BoxHeightVisibilityWidget({ distribution }) {
  const aspectRows = Array.isArray(distribution.aspect_ratio_distribution)
    ? distribution.aspect_ratio_distribution
    : [];
  const narrow = aspectRows.find((row) => row.bucket === "very_narrow");
  const wide = aspectRows.find((row) => row.bucket === "very_wide");
  const aspectNotes = [
    `${(numberOrZero(narrow?.percentage) * 100).toFixed(1)}% very narrow`,
    `${(numberOrZero(wide?.percentage) * 100).toFixed(1)}% very wide`
  ];

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Normalized Height</div>
        <BucketBars rows={distribution.height_distribution} emptyText="No box-height data yet." />
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Pixel Height Visibility</div>
        <BucketBars rows={distribution.pixel_visibility_distribution} emptyText="No pixel-visibility data yet." />
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
        Aspect ratio support check: {aspectNotes.join(" / ")}. Square or very wide people boxes may indicate partial-body labels or annotation issues.
      </div>
    </div>
  );
}

// Resolution is simplified on purpose: top groups plus "Other" gives enough signal
// for camera datasets without spending space on a large chart.
function ResolutionWidget({ resolutionSummary, totalImages }) {
  const topResolutions = Array.isArray(resolutionSummary.top_resolutions) ? resolutionSummary.top_resolutions : [];
  const totalCount = Math.max(0, totalImages);
  const topCount = topResolutions.reduce((sum, item) => sum + numberOrZero(item.count), 0);
  const otherCount = Math.max(0, totalCount - topCount);
  const rows = [...topResolutions.slice(0, 3)];

  if (otherCount > 0 || (!rows.length && totalCount === 0)) {
    rows.push({
      resolution: "Other",
      count: otherCount,
      ratio: totalCount > 0 ? otherCount / totalCount : 0
    });
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <MiniStat label="Dominant" value={resolutionSummary.most_common_resolution || "N/A"} />
        <MiniStat label="Dominant Ratio" value={`${(numberOrZero(resolutionSummary.dominant_ratio) * 100).toFixed(1)}%`} />
        <MiniStat label="Unique Resolutions" value={numberOrZero(resolutionSummary.unique_resolution_count)} />
      </div>
      <div className="space-y-3">
        {rows.length ? (
          rows.map((row) => (
            <MetricBar
              key={row.resolution}
              label={row.resolution}
              percentage={numberOrZero(row.ratio)}
              colorClass="bg-cyan-500"
              meta={`${numberOrZero(row.count)} images`}
            />
          ))
        ) : (
          <NoDataMessage>No resolution data yet.</NoDataMessage>
        )}
      </div>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-2 break-words text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function HelpTooltip({ title, body }) {
  return <Tooltip title={title} body={body} placement="bottom" />;
}

function EmptyPanel({ children }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">{children}</div>;
}

function NoDataMessage({ children }) {
  return <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">{children}</div>;
}

function numberOrZero(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function summarizeClassBalance(classBalance) {
  if (!classBalance.length) {
    return { tone: "yellow", text: "No class balance data available." };
  }

  const maxPercentage = Math.max(...classBalance.map((row) => numberOrZero(row.percentage)));
  if (maxPercentage > 0.8) {
    return { tone: "red", text: "Severely imbalanced dataset." };
  }
  if (maxPercentage > 0.65) {
    return { tone: "yellow", text: "Slight imbalance between the two classes." };
  }
  return { tone: "green", text: "Balanced dataset." };
}

function summarizeClassCoverage(classCoverage) {
  if (!classCoverage.length) {
    return { tone: "yellow", text: "No class coverage data available." };
  }

  const minCoverage = Math.min(...classCoverage.map((row) => numberOrZero(row.image_ratio)));
  if (minCoverage < 0.3) {
    return { tone: "red", text: "Class coverage is insufficient." };
  }
  if (minCoverage < 0.5) {
    return { tone: "yellow", text: "One class appears in fewer scenes." };
  }
  return { tone: "green", text: "Both classes well represented across images." };
}

function summarizeObjectDensity(distribution) {
  if (!distribution.length) {
    return { tone: "yellow", text: "No objects-per-image distribution available." };
  }

  const zeroBucket = distribution.find((item) => item.bucket === "0_objects");
  const denseBucket = distribution.find((item) => item.bucket === "gt_5_objects");
  const zeroRatio = numberOrZero(zeroBucket?.percentage);
  const denseRatio = numberOrZero(denseBucket?.percentage);

  if (zeroRatio > 0.4 || denseRatio > 0.45) {
    return { tone: "red", text: "Scene density is heavily skewed." };
  }
  if (zeroRatio > 0.2 || denseRatio > 0.3) {
    return { tone: "yellow", text: "Scene density may be too sparse or too crowded." };
  }
  return { tone: "green", text: "Object density looks balanced." };
}

function summarizeBoundingBoxes(distribution) {
  const totalBoxes = numberOrZero(distribution.total_boxes);
  if (!totalBoxes) {
    return { tone: "yellow", text: "No bounding-box analytics available." };
  }

  const tinyOrSmallRatio = numberOrZero(distribution.tiny_or_small_percentage);
  const lowHeightRatio = numberOrZero(distribution.low_height_percentage);
  const tooSmallPixelRatio = numberOrZero(distribution.too_small_pixel_percentage);
  const lowVisibilityRatio = numberOrZero(distribution.low_visibility_percentage);
  const goodVisibilityRatio = numberOrZero(distribution.good_visibility_percentage);

  if (tooSmallPixelRatio > 0.2 || (tinyOrSmallRatio > 0.7 && lowHeightRatio > 0.45)) {
    return {
      tone: "red",
      text: `${(tooSmallPixelRatio * 100).toFixed(0)}% of objects are below 15 px height; detection and classification may be difficult.`
    };
  }
  if (lowVisibilityRatio > 0.45 || tinyOrSmallRatio > 0.6 || lowHeightRatio > 0.5) {
    return {
      tone: "yellow",
      text: "Many objects are tiny, short, or under 30 px tall; staff/customer classification may be less reliable."
    };
  }
  if (goodVisibilityRatio >= 0.75) {
    return { tone: "green", text: "Object heights are generally healthy for staff/customer classification." };
  }
  return { tone: "green", text: "Most objects have usable box scale and pixel visibility for YOLO training." };
}

function summarizeResolution(summary) {
  const dominantRatio = numberOrZero(summary.dominant_ratio);
  if (dominantRatio < 0.7) {
    return { tone: "red", text: "Resolution mix is inconsistent." };
  }
  if (dominantRatio < 0.85) {
    return { tone: "yellow", text: "Resolution consistency is moderate." };
  }
  return { tone: "green", text: "Resolution is highly consistent." };
}
