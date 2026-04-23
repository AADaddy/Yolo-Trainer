import { useEffect, useState } from "react";
import Tooltip from "./Tooltip";

const yoloVersions = [
  { value: "YOLO8", label: "YOLO8" },
  { value: "YOLO11", label: "YOLO11" },
  { value: "YOLO26", label: "YOLO26 (Coming Soon)", disabled: true }
];
const modelSizes = ["n", "s", "m", "l", "x"];
const splitRatios = ["80/20", "90/10", "70/30"];
const optimizerOptions = ["AdamW", "SGD", "Adam", "RMSProp"];

// Tooltip copy doubles as the product explanation for each setting so the UI
// and expected training behavior stay aligned as parameters evolve.
const parameterHelp = {
  split_ratio: {
    title: "Split Ratio",
    lines: [
      "Controls the deterministic train/val split for the processed dataset.",
      "Changing it alters how many images land in training versus validation, but existing images stay in their hash bucket.",
      "Recommended default: 80/20.",
      "Use 90/10 when the dataset is small and you want more training data. Use 70/30 when you want a stronger validation signal."
    ]
  },
  epochs: {
    title: "Epochs",
    lines: [
      "Number of full training passes over the dataset.",
      "Higher values can improve convergence but increase runtime and overfitting risk.",
      "Recommended default: 100.",
      "Increase for larger or harder datasets. Decrease if validation metrics plateau early."
    ]
  },
  imgsz: {
    title: "Image Size",
    lines: [
      "Input image resolution used during training.",
      "Higher values help with small objects but need more GPU memory and time.",
      "Recommended default: 1280.",
      "Increase for tiny objects. Decrease if training is slow or memory-limited."
    ]
  },
  batch: {
    title: "Batch",
    lines: [
      "Number of images processed per optimizer step.",
      "Higher values can speed training but require more GPU memory.",
      "Recommended default: -1 (auto).",
      "Increase only if your GPU has headroom. Lower it if you hit out-of-memory errors."
    ]
  },
  workers: {
    title: "Workers",
    lines: [
      "CPU worker processes for loading training data.",
      "More workers can speed input loading but use more CPU and RAM.",
      "Recommended default: 2.",
      "Increase on strong CPUs. Decrease if Windows multiprocessing causes memory pressure."
    ]
  },
  cache: {
    title: "Cache",
    lines: [
      "Caches dataset images to speed up repeated access during training.",
      "Enabling it can improve throughput if enough RAM is available.",
      "Recommended default: True.",
      "Keep it on for local machines with enough memory. Turn it off if RAM becomes a bottleneck."
    ]
  },
  rect: {
    title: "Rect",
    lines: [
      "Uses rectangular batches to reduce padding waste for non-square images.",
      "This can improve efficiency and preserve aspect ratio characteristics.",
      "Recommended default: True.",
      "Leave it enabled unless you have a reason to force square batching."
    ]
  },
  optimizer: {
    title: "Optimizer",
    lines: [
      "Algorithm used to update model weights.",
      "Different optimizers can change convergence speed and stability.",
      "Recommended default: AdamW.",
      "Keep AdamW for general use. Try SGD only if you want to experiment and can retune learning rate behavior."
    ]
  },
  lr0: {
    title: "lr0",
    lines: [
      "Initial learning rate at the start of training.",
      "Too high can make training unstable; too low can slow convergence.",
      "Recommended default: 0.001.",
      "Increase cautiously if learning is too slow. Decrease if loss spikes or metrics fluctuate badly."
    ]
  },
  momentum: {
    title: "Momentum",
    lines: [
      "Smooths weight updates across training steps.",
      "Higher momentum can stabilize learning but may react more slowly to new gradients.",
      "Recommended default: 0.9.",
      "Keep near 0.9 for most cases. Lower slightly if training feels too sluggish."
    ]
  },
  device: {
    title: "Device",
    lines: [
      "Selects whether training runs on GPU or CPU.",
      "GPU is much faster for modern YOLO training.",
      "Recommended default: cuda.",
      "Use CPU only when a supported GPU is unavailable."
    ]
  },
  amp: {
    title: "AMP",
    lines: [
      "Automatic mixed precision uses lower precision math where safe.",
      "It usually speeds training and reduces GPU memory usage.",
      "Recommended default: True.",
      "Keep it enabled on GPU unless you suspect precision-related instability."
    ]
  },
  mosaic_enabled: {
    title: "Mosaic Augmentation",
    lines: [
      "Combines multiple images into one augmented training sample.",
      "Improves variation in object scale, position, and background, which often helps smaller datasets generalize.",
      "Recommended default: enabled.",
      "Consider disabling it when you want more natural-looking samples or stricter experiment control."
    ]
  },
  multiscale_enabled: {
    title: "Multi-scale Training",
    lines: [
      "Varies the effective image scale during training.",
      "Can improve robustness when object scale changes a lot between cameras or scenes.",
      "Recommended default: disabled initially.",
      "Enable for scale-heavy datasets; leave off for more controlled comparisons because it can increase variability and experiment complexity."
    ]
  }
};

const defaultForm = {
  dataset_version_id: "",
  split_ratio: "80/20",
  yolo_version: "YOLO11",
  model_size: "s",
  epochs: 100,
  imgsz: 1280,
  batch: -1,
  workers: 2,
  cache: true,
  rect: true,
  optimizer: "AdamW",
  lr0: 0.001,
  momentum: 0.9,
  device: "cuda",
  amp: true,
  mosaic_enabled: true,
  multiscale_enabled: false
};

export default function TrainingForm({ apiBase, selectedProject, datasets, onCreated }) {
  const [form, setForm] = useState(defaultForm);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadConfig() {
      if (!selectedProject) {
        setForm(defaultForm);
        return;
      }
      setLoading(true);
      try {
        const response = await fetch(`${apiBase}/training/config/${selectedProject.id}`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Unable to load training config.");
        }
        if (!cancelled) {
          setForm({ ...defaultForm, ...data, dataset_version_id: data.dataset_version_id || "" });
        }
      } catch (error) {
        if (!cancelled) {
          setStatus(error.message || "Unable to load saved training config.");
          setForm(defaultForm);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadConfig();
    return () => {
      cancelled = true;
    };
  }, [apiBase, selectedProject?.id]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedProject) return;
    const selectedYoloVersion = yoloVersions.find((version) => version.value === form.yolo_version);
    if (selectedYoloVersion?.disabled) {
      setStatus("YOLO26 is a future placeholder. Add matching yolo26*.pt weights before training with it.");
      return;
    }
    setStatus("Starting training run...");
    const response = await fetch(`${apiBase}/training/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        project_id: selectedProject.id,
        dataset_version_id: Number(form.dataset_version_id),
        epochs: Number(form.epochs),
        imgsz: Number(form.imgsz),
        batch: Number(form.batch),
        workers: Number(form.workers),
        lr0: Number(form.lr0),
        momentum: Number(form.momentum)
      })
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus(data.detail || "Unable to start training.");
      return;
    }
    setStatus(`Training run ${data.run_name} queued.`);
    onCreated();
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl bg-white p-6 shadow-sm">
      <h3 className="text-lg font-semibold">Training Configuration</h3>
      <p className="mt-2 text-sm text-slate-500">
        The last saved config loads per project. Changes are only saved when you click `Start Training`.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Field label="Dataset Version">
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
            value={form.dataset_version_id}
            onChange={(event) => setForm({ ...form, dataset_version_id: event.target.value })}
            required
            disabled={loading}
          >
            <option value="">Select dataset</option>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.version}
              </option>
            ))}
          </select>
        </Field>
        <TooltipField label="Split Ratio" help={parameterHelp.split_ratio}>
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
            value={form.split_ratio}
            onChange={(event) => setForm({ ...form, split_ratio: event.target.value })}
          >
            {splitRatios.map((ratio) => (
              <option key={ratio} value={ratio}>
                {ratio}
              </option>
            ))}
          </select>
        </TooltipField>
        <Field label="YOLO Version">
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
            value={form.yolo_version}
            onChange={(event) => setForm({ ...form, yolo_version: event.target.value })}
          >
            {yoloVersions.map((version) => (
              <option key={version.value} value={version.value} disabled={version.disabled}>
                {version.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model Size">
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
            value={form.model_size}
            onChange={(event) => setForm({ ...form, model_size: event.target.value })}
          >
            {modelSizes.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </Field>
        <TooltipNumberField label="Epochs" help={parameterHelp.epochs} value={form.epochs} onChange={(value) => setForm({ ...form, epochs: value })} />
        <TooltipNumberField label="Image Size" help={parameterHelp.imgsz} value={form.imgsz} onChange={(value) => setForm({ ...form, imgsz: value })} />
        <TooltipNumberField label="Batch" help={parameterHelp.batch} value={form.batch} onChange={(value) => setForm({ ...form, batch: value })} />
        <TooltipNumberField label="Workers" help={parameterHelp.workers} value={form.workers} onChange={(value) => setForm({ ...form, workers: value })} />
        <TooltipField label="Cache" help={parameterHelp.cache}>
          <BooleanSelect value={form.cache} onChange={(value) => setForm({ ...form, cache: value })} />
        </TooltipField>
        <TooltipField label="Rect" help={parameterHelp.rect}>
          <BooleanSelect value={form.rect} onChange={(value) => setForm({ ...form, rect: value })} />
        </TooltipField>
        <TooltipField label="Optimizer" help={parameterHelp.optimizer}>
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
            value={form.optimizer}
            onChange={(event) => setForm({ ...form, optimizer: event.target.value })}
          >
            {optimizerOptions.map((optimizer) => (
              <option key={optimizer} value={optimizer}>
                {optimizer}
              </option>
            ))}
          </select>
        </TooltipField>
        <TooltipNumberField
          label="lr0"
          help={parameterHelp.lr0}
          step="0.001"
          value={form.lr0}
          onChange={(value) => setForm({ ...form, lr0: value })}
        />
        <TooltipNumberField
          label="Momentum"
          help={parameterHelp.momentum}
          step="0.1"
          value={form.momentum}
          onChange={(value) => setForm({ ...form, momentum: value })}
        />
        <TooltipField label="Device" help={parameterHelp.device}>
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
            value={form.device}
            onChange={(event) => setForm({ ...form, device: event.target.value })}
          >
            <option value="cuda">cuda</option>
            <option value="cpu">cpu</option>
          </select>
        </TooltipField>
        <TooltipField label="AMP" help={parameterHelp.amp}>
          <BooleanSelect value={form.amp} onChange={(value) => setForm({ ...form, amp: value })} />
        </TooltipField>
      </div>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Advanced Training Options</h4>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <ToggleField
            label="Mosaic Augmentation"
            help={parameterHelp.mosaic_enabled}
            checked={form.mosaic_enabled}
            onChange={(value) => setForm({ ...form, mosaic_enabled: value })}
          />
          <ToggleField
            label="Multi-scale Training"
            help={parameterHelp.multiscale_enabled}
            checked={form.multiscale_enabled}
            onChange={(value) => setForm({ ...form, multiscale_enabled: value })}
          />
        </div>
      </section>
      <button className="mt-6 rounded-xl bg-accent px-5 py-3 font-medium text-white" disabled={loading}>
        Start Training
      </button>
      <div className="mt-3 text-sm text-slate-500">{status}</div>
    </form>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      <span className="mb-2 block">{label}</span>
      {children}
    </label>
  );
}

function TooltipField({ label, help, children }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      <span className="mb-2 flex items-center gap-2">
        <span>{label}</span>
        <HelpTooltip help={help} />
      </span>
      {children}
    </label>
  );
}

function TooltipNumberField({ label, help, value, onChange, step = "1" }) {
  return (
    <TooltipField label={label} help={help}>
      <input
        className="w-full rounded-xl border border-slate-200 px-3 py-2"
        type="number"
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </TooltipField>
  );
}

function BooleanSelect({ value, onChange }) {
  return (
    <select
      className="w-full rounded-xl border border-slate-200 px-3 py-2"
      value={value ? "true" : "false"}
      onChange={(event) => onChange(event.target.value === "true")}
    >
      <option value="true">True</option>
      <option value="false">False</option>
    </select>
  );
}

function ToggleField({ label, help, checked, onChange }) {
  return (
    <label className="flex min-h-24 items-start justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 text-sm font-medium text-slate-700">
      <span>
        <span className="mb-2 flex items-center gap-2">
          <span>{label}</span>
          <HelpTooltip help={help} />
        </span>
        <span className="block text-xs font-normal text-slate-500">{checked ? "Enabled" : "Disabled"}</span>
      </span>
      <input
        type="checkbox"
        className="mt-1 h-5 w-5 accent-blue-600"
        checked={!!checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}

function HelpTooltip({ help }) {
  return (
    <Tooltip
      content={
        <div className="font-normal">
          <div className="font-semibold">{help.title}</div>
          <div className="mt-2 space-y-1">
            {help.lines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </div>
      }
      placement="bottom"
    />
  );
}
