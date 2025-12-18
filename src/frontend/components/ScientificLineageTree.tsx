
'use client';

import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

interface NodeData {
    id: string;
    label: string;
    group: string;
    val: number;
    breeder?: string;
    type?: string;
    description?: string;
    image?: string;
    children?: NodeData[];
    _children?: NodeData[];
}

interface TreeProps {
    data: any;
    onNodeClick: (node: NodeData) => void;
    selectedNodeId?: string;
}

export default function ScientificLineageTree({ data, onNodeClick, selectedNodeId }: TreeProps) {
    const svgRef = useRef<SVGSVGElement>(null);
    const wrapperRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

    // Build Hierarchy Helper
    // For Ancestors: Target -> Parents
    // For Descendants: Target -> Children
    const buildTreeData = (nodes: any[], links: any[], rootId: string, direction: 'ancestors' | 'descendants') => {
        const rootNode = nodes.find(n => n.id === rootId);
        if (!rootNode) return null;

        // Deep clone to avoid mutating shared refs if we run this twice
        const nodeMap = new Map(nodes.map(n => [n.id, { ...n, children: [] }]));

        links.forEach(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            // Logic for Ancestors:
            // "White Widow" (Source/Child) <- bred from <- "Brazil Sativa" (Target/Parent)
            // Visual Tree: Root (White Widow) -> Child (Brazil Sativa) [Right Side]
            // Matches: sourceId (White Widow) -> targetId (Brazil Sativa)

            if (direction === 'ancestors') {
                // We want Target -> Parent logic
                // If data link says: Source (Child) -> Target (Parent)
                // Then hierarchy: Node(Source).children.push(Node(Target))
                if (sourceId && targetId && nodeMap.has(sourceId) && nodeMap.has(targetId)) {
                    // Check relation type or assume standard link direction from API?
                    // API returns: Bred From Target. So Source is Child.
                    // Filter only ancestor links? 
                    // Or rely on the 'group' logic?
                    // Let's rely on nodeMap connectivity from root.
                    const parent = nodeMap.get(sourceId);
                    const child = nodeMap.get(targetId);
                    // Prevent cyclic or wrong-way links?
                    // Only add if child is NOT 'Descendant' group?
                    if (activeLinkStr(link, 'ancestor')) {
                        parent?.children.push(child);
                    }
                }
            } else {
                // Logic for Descendants (Left Side)
                // We want Target -> Child logic
                // API Link: Source (Child) -> Target (StartNode/Parent)
                // We want: StartNode (Parent) -> Child
                // So: Node(Target).children.push(Node(Source))
                if (sourceId && targetId && nodeMap.has(sourceId) && nodeMap.has(targetId)) {
                    if (activeLinkStr(link, 'descendant')) {
                        const parent = nodeMap.get(targetId); // Start Node
                        const child = nodeMap.get(sourceId);  // Descendant
                        parent?.children.push(child);
                    }
                }
            }
        });

        return nodeMap.get(rootId);
    };

    const activeLinkStr = (link: any, dir: 'ancestor' | 'descendant') => {
        // Simple heuristic: 
        // Ancestor: Target of link should be Ancestor/Inferred/Relative
        // Descendant: Source of link should be Descendant
        // (Based on how we constructed links in backend)

        const targetGroup = typeof link.target === 'object' ? link.target.group : (data.nodes.find((n: any) => n.id === link.target)?.group);
        const sourceGroup = typeof link.source === 'object' ? link.source.group : (data.nodes.find((n: any) => n.id === link.source)?.group);

        if (dir === 'ancestor') {
            // Standard links: Child -> Parent. Parent is target.
            return targetGroup !== 'Descendant';
        } else {
            // Descendant links: Descendant -> Parent. Descendant is source.
            return sourceGroup === 'Descendant';
        }
    };


    useEffect(() => {
        if (!wrapperRef.current) return;
        const resizeObserver = new ResizeObserver(entries => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0) setDimensions({ width, height });
            }
        });
        resizeObserver.observe(wrapperRef.current);
        return () => resizeObserver.disconnect();
    }, []);

    useEffect(() => {
        if (!data.nodes.length || !svgRef.current) return;

        const targetNode = data.nodes.find((n: any) => n.group === 'Target') || data.nodes[0];
        if (!targetNode) return;

        // 1. Build TWO trees
        const ancestorRootData = buildTreeData(data.nodes, data.links, targetNode.id, 'ancestors');
        const descendantRootData = buildTreeData(data.nodes, data.links, targetNode.id, 'descendants');

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        const g = svg.append('g');

        // Layout Settings
        const nodeWidth = 220;
        const nodeHeight = 60;
        const padding = 120; // Horizontal separation

        // Tree Function
        const treeLayout = d3.tree<NodeData>()
            .nodeSize([80, 250]) // [height, width] - separation
            .separation((a, b) => a.parent === b.parent ? 1.1 : 1.3);

        // --- Render Ancestors (Right) ---
        let ancestorNodes: any[] = [];
        let ancestorLinks: any[] = [];

        if (ancestorRootData) {
            const root = d3.hierarchy<NodeData>(ancestorRootData);
            treeLayout(root);

            // Should stay as is (Right direction)
            ancestorNodes = root.descendants();
            ancestorLinks = root.links();
        }

        // --- Render Descendants (Left) ---
        let descendantNodes: any[] = [];
        let descendantLinks: any[] = [];

        if (descendantRootData) {
            const root = d3.hierarchy<NodeData>(descendantRootData);
            treeLayout(root);

            // FLIP Coordinates for Left Direction
            root.descendants().forEach((d: any) => {
                d.y = -d.y; // Flip horizontal
            });

            // Remove the Root itself from Descendants array to avoid duplicating the center node visual
            // But we need links to it. 
            // Better: Render all, but filters checks.
            descendantNodes = root.descendants().filter(d => d.data.id !== targetNode.id); // Skip root, we draw it in ancestors (or once)
            descendantLinks = root.links();
        }

        // Filter ancestor Root if we want to draw it uniquely? 
        // No, let ancestor tree draw the root. Descendant tree nodes join to it.
        // We need to adjust Descendant Links to point to the Ancestor Root (which is at 0,0 locally)
        // Since we filtered root out of nodes, we use the root from ancestorNodes (which is at x,y)
        // Actually, d3.tree places root at 0,0 usually (before translation). 
        // So they align perfectly at (0,0).

        const linkGen = d3.linkHorizontal<any, any>()
            .x(d => d.y)
            .y(d => d.x);

        // Draw Links
        const allLinks = [...ancestorLinks, ...descendantLinks];
        g.selectAll('.link')
            .data(allLinks)
            .enter().append('path')
            .attr('class', 'link')
            .attr('d', linkGen)
            .attr('fill', 'none')
            .attr('stroke', '#cbd5e1')
            .attr('stroke-width', 1.5);

        // Draw Nodes
        const allNodes = [...ancestorNodes, ...descendantNodes];
        const nodeGroups = g.selectAll('.node')
            .data(allNodes)
            .enter().append('g')
            .attr('class', 'node cursor-pointer')
            .attr('transform', (d: any) => `translate(${d.y},${d.x})`)
            .on('click', (event, d: any) => {
                event.stopPropagation();
                onNodeClick(d.data);
            });

        // Rect
        nodeGroups.append('rect')
            .attr('x', -100)
            .attr('y', -30)
            .attr('width', 200)
            .attr('height', 60)
            .attr('rx', 8)
            .attr('fill', (d: any) => {
                if (d.data.id === selectedNodeId) return '#dcfce7'; // Selected (Green-100)
                if (d.data.group === 'Target') return '#f0fdf4'; // Target default
                return '#ffffff';
            })
            .attr('stroke', (d: any) => {
                if (d.data.id === selectedNodeId) return '#16a34a'; // Selected (Green-600)
                if (d.data.group === 'Target') return '#22c55e';
                return '#94a3b8';
            })
            .attr('stroke-width', (d: any) => d.data.id === selectedNodeId || d.data.group === 'Target' ? 2 : 1)
            .attr('class', 'transition-colors duration-200 shadow-sm hover:shadow-md');

        // Label
        nodeGroups.append('text')
            .attr('dy', -5)
            .attr('text-anchor', 'middle')
            .style('font-weight', '600')
            .style('font-size', '14px')
            .style('fill', '#1e293b')
            .text((d: any) => d.data.label.length > 22 ? d.data.label.substring(0, 20) + '...' : d.data.label);

        // Subtitle
        nodeGroups.append('text')
            .attr('dy', 15)
            .attr('text-anchor', 'middle')
            .style('font-size', '11px')
            .style('fill', '#64748b')
            .text((d: any) => {
                // Format: [Group] • [Breeder]
                const role = d.data.group === 'Descendant' ? 'Crossed From' : (d.data.group === 'Ancestor' ? 'Ancestor' : 'Strain');
                const breeder = d.data.breeder || '';
                return `${role} ${breeder ? '• ' + breeder : ''}`.substring(0, 30);
            });

        // Setup Zoom
        const zoom = d3.zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.1, 3])
            .on('zoom', (event) => g.attr('transform', event.transform));

        zoomRef.current = zoom;
        svg.call(zoom);

        // Auto Fit
        try {
            const bbox = g.node()?.getBBox();
            if (bbox) {
                const { width, height } = dimensions;
                const scale = Math.min(
                    0.9,
                    0.9 / Math.max(bbox.width / width, bbox.height / height)
                );
                // Center logic
                const tx = width / 2 - (bbox.x + bbox.width / 2) * scale;
                const ty = height / 2 - (bbox.y + bbox.height / 2) * scale;

                svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
            }
        } catch (e) {
            // Fallback
            svg.call(zoom.transform, d3.zoomIdentity.translate(dimensions.width / 2, dimensions.height / 2).scale(0.6));
        }

    }, [data, dimensions, selectedNodeId]);

    return (
        <div ref={wrapperRef} className="w-full h-full bg-slate-50 relative overflow-hidden">
            {/* Legend or Badge */}
            <div className="absolute top-4 right-4 z-10 pointer-events-none">
                <span className="px-2 py-1 bg-white/80 backdrop-blur border border-green-200 text-green-700 text-xs font-bold rounded shadow-sm">
                    Scientific Mode
                </span>
            </div>
            <svg ref={svgRef} className="w-full h-full" />
        </div>
    );
}
