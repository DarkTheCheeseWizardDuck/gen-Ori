import { Locales } from './locales.js';


/**
 * Helper to create an SVG element with attributes
 */
function makeSvg(tag, attrs) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const k in attrs) {
        el.setAttribute(k, attrs[k]);
    }
    return el;
}

// 1. Normalizes the Python keys (v, v1, v2) to the JS render keys (xy, xy1, xy2), and extends reference creases to boundaries
function normalizeRefs(rawRefs) {
    let refs = rawRefs;
    
    // Safely parse if it arrived as a string
    if (typeof refs === 'string') {
        try { refs = JSON.parse(refs); } 
        catch (e) { return []; }
    }
    
    if (!Array.isArray(refs)) return [];

    // Helper to extend any segment to the borders of the [0, 1] unit square
    const extendToBoundary = (p1, p2) => {
        const EPS = 1e-9;
        const dx = p2[0] - p1[0];
        const dy = p2[1] - p1[1];
        
        // If it's a zero-length line, do nothing
        if (Math.abs(dx) < EPS && Math.abs(dy) < EPS) return [p1, p2];

        const pts = [];
        const addPoint = (t) => {
            const x = p1[0] + t * dx;
            const y = p1[1] + t * dy;
            // Check if intersection is within the unit square bounds
            if (x >= -EPS && x <= 1 + EPS && y >= -EPS && y <= 1 + EPS) {
                // Deduplicate against already found points (handles corner intersections)
                if (!pts.some(p => Math.hypot(p[0] - x, p[1] - y) < 1e-6)) {
                    pts.push([x, y]);
                }
            }
        };

        // Find intersections with vertical borders (x=0, x=1)
        if (Math.abs(dx) > EPS) {
            addPoint(-p1[0] / dx);
            addPoint((1 - p1[0]) / dx);
        }
        // Find intersections with horizontal borders (y=0, y=1)
        if (Math.abs(dy) > EPS) {
            addPoint(-p1[1] / dy);
            addPoint((1 - p1[1]) / dy);
        }

        // Return the two boundary points, or fallback to original if math fails
        return pts.length >= 2 ? [pts[0], pts[1]] : [p1, p2];
    };
    
    return refs.map(ref => {
        if (ref.type === 'vertex') {
            return {
                type: 'vertex', xy: ref.xy || ref.v,
                originKind: ref.origin_kind, originStep: ref.origin_step,
            };
        } else if (ref.type === 'crease' || ref.type === 'edge') {
            let xy1 = ref.xy1 || ref.v1;
            let xy2 = ref.xy2 || ref.v2;

            if (xy1 && xy2) {
                const extended = extendToBoundary(xy1, xy2);
                xy1 = extended[0];
                xy2 = extended[1];
            }

            return { type: ref.type, xy1: xy1, xy2: xy2 };
        }
        return ref;
    });
}

// 2. Accumulates creases across the ancestry tree
function processAncestry(ancestryArray) {
    const steps = [];
    // Start with the border of the unit square
    const accumulatedCreases = [
        [[0, 0], [1, 0]], [[1, 0], [1, 1]], [[1, 1], [0, 1]], [[0, 1], [0, 0]]
    ];

    for (const entry of ancestryArray) {
        if (entry.function_name === 'root') continue;

        // Extract the pre-transformed floats directly
        const nc1 = entry.new_crease_v1;
        const nc2 = entry.new_crease_v2;
        const refs = normalizeRefs(entry.refs);
        
        // Snapshot the paper state BEFORE this step's crease is folded
        const currentCreases = [...accumulatedCreases];

        steps.push({
            depth: entry.depth,
            function_name: entry.function_name,
            pastCreases: currentCreases,
            newCrease: nc1 && nc2 ? [nc1, nc2] : null,
            refs: refs
        });

        // Add this step's crease to the background for all subsequent steps
        if (nc1 && nc2 && (nc1[0] !== nc2[0] || nc1[1] !== nc2[1])) {
            accumulatedCreases.push([nc1, nc2]);
        }
    }
    return steps;
}

// 3. Translates the Python _instruction function
function getInstructionText(fn, refs) {
    const lang = localStorage.getItem('explori_lang') || 'en';
    const dict = Locales[lang] || Locales['en'];

    // When a circled point was created by an earlier step in this same
    // sequence, name that step instead of leaving the point unexplained.
    const stepRefText = (ref) => {
        if (ref && ref.originKind === 'step' && ref.originStep != null) {
            return String(ref.originStep);
        }
        return null;
    };

    // Phrase for one side of an "intersection of X and Y" description.
    // originStep here is a single label: 0 = a border edge, N = step N.
    const lineLabelText = (label) => {
        if (label === 0) return dict.lineEdge;
        if (label === -1) return dict.lineDiagonal || dict.lineEdge;
        return (dict.lineStepTemplate || "step {n}").replace('{n}', label);
    };

    // When a circled point isn't itself a tracked step, but sits where two
    // already-drawn lines cross, describe it that way instead of leaving it
    // unexplained.
    const intersectionText = (ref, diagTemplate, edgeTemplateKey) => {
        if (!ref || ref.originKind !== 'intersection' || !Array.isArray(ref.originStep)) {
            return null;
        }
        const [a, b] = ref.originStep;
        const template = dict[edgeTemplateKey];
        if (!template) return null;
        return template.replace('{a}', lineLabelText(a)).replace('{b}', lineLabelText(b));
    };

    // Describe a single circled point by whatever we know about its origin:
    // a corner, an earlier step's endpoint, an intersection of two already-
    // drawn lines, or (last resort) just "the circled point".
    const describePoint = (ref) => {
        if (!ref) return dict.linePoint || "the circled point";
        if (ref.originKind === 'corner') return dict.lineCorner || "the corner";
        const step = stepRefText(ref);
        if (step) {
            return (dict.linePointStepTemplate || "the point from step {n}").replace('{n}', step);
        }
        if (ref.originKind === 'intersection' && Array.isArray(ref.originStep)) {
            const [a, b] = ref.originStep;
            return (dict.lineIntersectionTemplate || "the intersection of {a} and {b}")
                .replace('{a}', lineLabelText(a)).replace('{b}', lineLabelText(b));
        }
        return dict.linePoint || "the circled point";
    };

    if (!fn || fn === "target") return dict.instrTarget;
    if (fn === "vertex_pair") {
        const vertexRefs = refs.filter(r => r.type === 'vertex');
        if (vertexRefs.length === 2) {
            const [a, b] = vertexRefs.map(describePoint);
            return (dict.instrVertexPairBoth || "Crease through {a} and {b}.")
                .replace('{a}', a).replace('{b}', b);
        }
        return dict.instrVertexPair;
    }
    if (fn === "parallel_bisector") return dict.instrParallelBisector;
    if (fn === "angle_bisector") return dict.instrAngleBisector;
    
    if (fn === "perp_through_vertex") {
        const hasDiag = refs.some(r => r.type === 'crease');
        const vertexRef = refs.find(r => r.type === 'vertex');
        const n = stepRefText(vertexRef);
        if (n) {
            const template = hasDiag ? dict.instrPerpDiagStep : dict.instrPerpEdgeStep;
            if (template) return template.replace('{n}', n);
        }
        const intersectKey = hasDiag ? 'instrPerpDiagIntersect' : 'instrPerpEdgeIntersect';
        const intersectText = intersectionText(vertexRef, null, intersectKey);
        if (intersectText) return intersectText;
        return hasDiag ? dict.instrPerpDiag : dict.instrPerpEdge;
    }
    
    // Fallback for undefined functions (capitalizes and replaces underscores)
    return fn.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase()) + ".";
}

// 4. Draws a single step to an SVG
function renderStepSvg(svg, step, width, height, isFinal = false, targetXY = null) {
    svg.innerHTML = '';
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.style.display = "block";
    svg.style.margin = "0 auto";

    const scale = Math.min(width, height) * 0.9;
    const padX = (width - scale) / 2;
    const padY = (height - scale) / 2;
    
    const FLIP_Y = true; 

    const tx = (x) => padX + (x * scale);
    const ty = (y) => FLIP_Y ? height - (padY + (y * scale)) : padY + (y * scale);

    // Helper to safely draw lines
    const drawLine = (p1, p2, stroke, strokeWidth, dashed = false) => {
        if (!p1 || !p2) return;
        const attrs = {
            x1: tx(p1[0]), y1: ty(p1[1]), x2: tx(p2[0]), y2: ty(p2[1]),
            stroke: stroke, "stroke-width": strokeWidth
        };
        if (dashed) attrs["stroke-dasharray"] = "10 6";
        svg.appendChild(makeSvg("line", attrs));
    };

    // A. Draw Past Creases (Gray)
    for (const [p1, p2] of step.pastCreases) {
        drawLine(p1, p2, "var(--cp-h)", "1");
    }

    if (!isFinal) {
        // B. Reference Lines (Dashed Green/Accent)
        for (const ref of step.refs) {
            if (ref.type === 'crease' || ref.type === 'edge') {
                drawLine(ref.xy1, ref.xy2, "var(--packing-h)", "4", true);
            }
        }

        // C. New Crease
        if (step.newCrease) {
            drawLine(step.newCrease[0], step.newCrease[1], "var(--accent)", "4");
        }

        // D. Reference Vertices (Hollow circles)
        for (const ref of step.refs) {
            if (ref.type === 'vertex' && ref.xy) {
                svg.appendChild(makeSvg("circle", {
                    cx: tx(ref.xy[0]), cy: ty(ref.xy[1]), r: "8",
                    fill: "none", stroke: "var(--accent)", "stroke-width": "3"
                }));
            }
        }
    } else if (targetXY) {
        // E. Final Target Dot
        svg.appendChild(makeSvg("circle", {
            cx: tx(targetXY[0]), cy: ty(targetXY[1]), r: "8",
            fill: "var(--node-fill)", stroke: "var(--node-stroke)", "stroke-width": "2"
        }));
    }
}

// 5. Main Workspace Populator
export function renderReferenceWorkspace(ancestryArray, targetXY = null) {
    const workspace = document.getElementById("refsWorkspace");
    if (!workspace || !Array.isArray(ancestryArray)) return;

    workspace.innerHTML = '';
    workspace.style.display = "flex";
    workspace.style.flexWrap = "wrap";
    workspace.style.gap = "1rem";

    // Legend: explains the visual language once, since past creases / the new
    // crease / reference lines / reference points otherwise only differ by
    // subtle color and thickness, which isn't self-explanatory at a glance.
    const legend = document.createElement("div");
    legend.className = "refs-legend";
    const legendItems = [
        { swatch: "line", color: "var(--cp-h)", width: "1", dashed: false, label: "Existing crease" },
        { swatch: "line", color: "var(--accent)", width: "4", dashed: false, label: "New crease (this step)" },
        { swatch: "line", color: "var(--packing-h)", width: "4", dashed: true, label: "Reference line" },
        { swatch: "circle", color: "var(--accent)", label: "Reference point" },
    ];
    for (const item of legendItems) {
        const entry = document.createElement("span");
        entry.className = "refs-legend-item";
        if (item.swatch === "line") {
            entry.innerHTML =
                `<svg width="24" height="12" viewBox="0 0 24 12">` +
                `<line x1="1" y1="6" x2="23" y2="6" stroke="${item.color}" stroke-width="${item.width}" ` +
                (item.dashed ? `stroke-dasharray="4 3"` : "") + `/></svg> ${item.label}`;
        } else {
            entry.innerHTML =
                `<svg width="14" height="14" viewBox="0 0 14 14">` +
                `<circle cx="7" cy="7" r="5" fill="none" stroke="${item.color}" stroke-width="2"/></svg> ${item.label}`;
        }
        legend.appendChild(entry);
    }
    workspace.appendChild(legend);

    const steps = processAncestry(ancestryArray);
    
    // Add the final target step so the last crease remains visible behind the dot
    if (steps.length > 0) {
        const lastStep = steps[steps.length - 1];
        if (lastStep.newCrease) {
            steps.push({ 
                function_name: 'target',
                isFinal: true, 
                pastCreases: lastStep.pastCreases.concat([lastStep.newCrease]),
                refs: []
            });
        }
    }

    steps.forEach((step, index) => {
        const stepDiv = document.createElement("div");
        stepDiv.className = "ref-step-container";
        stepDiv.style.width = "220px";
        stepDiv.style.textAlign = "center";

        const svg = makeSvg("svg", { width: "220", height: "220" });
        stepDiv.appendChild(svg);

        renderStepSvg(svg, step, 220, 220, step.isFinal, targetXY);

        const caption = document.createElement("div");
        caption.style.fontSize = "0.85rem";
        caption.style.marginTop = "0.5rem";
        caption.style.color = "var(--text-main, #d8d8e8)";
        
        const instruction = getInstructionText(step.function_name, step.refs || []);
        caption.innerHTML = `<strong>${index + 1}.</strong> ${instruction}`;
        
        stepDiv.appendChild(caption);
        workspace.appendChild(stepDiv);
    });
}