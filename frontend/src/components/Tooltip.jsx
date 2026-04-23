import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const VIEWPORT_MARGIN = 12;
const TRIGGER_GAP = 8;

export default function Tooltip({
  title,
  body,
  content,
  children,
  placement = "top",
  maxWidth = 288
}) {
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);
  const closeTimerRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0, placement, width: maxWidth });

  const tooltipContent = content ?? (
    <>
      {title ? <div className="font-semibold">{title}</div> : null}
      {body ? <div className={title ? "mt-2 leading-5 text-slate-100" : "leading-5"}>{body}</div> : null}
    </>
  );

  function showTooltip() {
    window.clearTimeout(closeTimerRef.current);
    setOpen(true);
  }

  function hideTooltip() {
    window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 80);
  }

  useEffect(() => {
    if (!open) return undefined;

    function updatePosition() {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const safeWidth = Math.min(maxWidth, window.innerWidth - VIEWPORT_MARGIN * 2);
      const estimatedHeight = tooltipRef.current?.offsetHeight || 160;
      const preferredTop =
        placement === "bottom" ? rect.bottom + TRIGGER_GAP : rect.top - estimatedHeight - TRIGGER_GAP;
      const shouldFlipToBottom = preferredTop < VIEWPORT_MARGIN;
      const shouldFlipToTop = placement === "bottom" && rect.bottom + estimatedHeight + TRIGGER_GAP > window.innerHeight - VIEWPORT_MARGIN;
      const resolvedPlacement = shouldFlipToBottom ? "bottom" : shouldFlipToTop ? "top" : placement;
      const top =
        resolvedPlacement === "bottom"
          ? rect.bottom + TRIGGER_GAP
          : Math.max(VIEWPORT_MARGIN, rect.top - estimatedHeight - TRIGGER_GAP);
      const centeredLeft = rect.left + rect.width / 2 - safeWidth / 2;
      const left = Math.min(
        window.innerWidth - safeWidth - VIEWPORT_MARGIN,
        Math.max(VIEWPORT_MARGIN, centeredLeft)
      );

      // The tooltip is portaled to the body because z-index cannot escape a
      // parent with overflow clipping; fixed viewport coordinates keep it aligned.
      setPosition({ left, top, placement: resolvedPlacement, width: safeWidth });
    }

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [maxWidth, open, placement]);

  useEffect(() => {
    return () => window.clearTimeout(closeTimerRef.current);
  }, []);

  return (
    <>
      <span
        ref={triggerRef}
        className="inline-flex"
        onClick={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
      >
        {children ?? (
          <span
            tabIndex={0}
            className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-300 text-xs text-slate-500"
            aria-label="Show help"
          >
            ?
          </span>
        )}
      </span>
      {open && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={tooltipRef}
              className="pointer-events-none fixed z-[10000] whitespace-pre-line rounded-xl bg-slate-900 p-3 text-xs leading-5 text-white shadow-xl"
              style={{ left: `${position.left}px`, top: `${position.top}px`, maxWidth: `${position.width}px` }}
              role="tooltip"
            >
              {tooltipContent}
            </div>,
            document.body
          )
        : null}
    </>
  );
}
