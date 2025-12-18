
'use client';

import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { ZoomIn, ZoomOut, Maximize } from 'lucide-react';

interface NodeData {
    id: string;
    label: string;
    group: string;
    val: number;
    breeder?: string;
    thc?: string;
    cbd?: string;
    type?: string;
    description?: string;
    effects?: string;
    flavor?: string;
    image?: string;
    children?: NodeData[];
    _children?: NodeData[]; // For collapsing
}

interface TreeProps {
    data: any; // Raw graph data from API { nodes: [], links: [] }
    onNodeClick: (node: NodeData) => void;
}

export default function ScientificLineageTree({ data, onNodeClick }: TreeProps) {
    const svgRef = useRef<SVGSVGElement>(null);
    const wrapperRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

    // Transform flat graph to hierarchy
    const buildHierarchy = (nodes: any[], links: any[]) => {
        if (!nodes.length) return null;

        // Find root (Target)
        const rootNode = nodes.find(n => n.group === 'Target') || nodes[0];
        if (!rootNode) return null;

        const idToNode = new Map(nodes.map(n => [n.id, { ...n, children: [] }]));

        links.forEach(link => {
            // Source is Child, Target is Parent (in "bred_from" relation context usually)
            // But we want to display Ancestors -> Child?
            // "White Widow" (Target) is bred from "Brazil Sativa" (Ancestor).
            // So visual hierarchy: Ancestor -> Target.

            // However, standard tree usually has Root = Selected Strain, and branches = relations?
            // If we want a Pedigree chart (Ancestors), it goes Right to Left or Bottom to Top.
            // If we use standard tree, Root is usually at top/left.

            // Let's visualize: Root (Target) splits into Parents.
            // So Target is "parent" in the data structure, and its physical parents are "children" in the tree structure.

            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            // If we want Target to be the root of the tree:
            // We find links where Source = Target ID.

            const parentNode = idToNode.get(sourceId); // The child in biological terms (White Widow)
            const childNode = idToNode.get(targetId);   // The biological parent (Brazil Sativa)

            if (parentNode && childNode) {
                parentNode.children.push(childNode);
            }
        });

        return idToNode.get(rootNode.id);
    };

    useEffect(() => {
        if (!data.nodes.length || !svgRef.current) return;

        const updateDimensions = () => {
            if (wrapperRef.current) {
                setDimensions({
                    width: wrapperRef.current.clientWidth,
                    height: wrapperRef.current.clientHeight
                });
            }
        };

        window.addEventListener('resize', updateDimensions);
        updateDimensions();

        const rootData = buildHierarchy(data.nodes, data.links);
        if (!rootData) return;

        const hierarchy = d3.hierarchy<NodeData>(rootData);

        // Layout Config
        const nodeWidth = 220;
        const nodeHeight = 80;
        const padding = 50;

        // Tree Layout (Horizontal)
        const treeLayout = d3.tree<NodeData>()
            .nodeSize([nodeHeight + padding, nodeWidth + padding])
            .separation((a, b) => a.parent === b.parent ? 1.2 : 1.5);

        const root = treeLayout(hierarchy);

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove(); // Clear previous

        const g = svg.append('g')
            .attr('transform', `translate(${dimensions.width / 2}, ${dimensions.height / 2})`);

        // Zoom capability
        const zoom = d3.zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });

        svg.call(zoom);

        // Center the tree initially
        // Initial transform to center the root node roughly
        // root.x is vertical, root.y is horizontal in this layout logic if we swap them
        // Let's draw standard horizontal tree: x=y, y=x swap

        const linkGen = d3.linkHorizontal<d3.HierarchyPointLink<NodeData>, d3.HierarchyPointNode<NodeData>>()
            .x(d => d.y)
            .y(d => d.x);

        // Links
        g.selectAll('.link')
            .data(root.links())
            .enter()
            .append('path')
            .attr('class', 'link')
            .attr('d', linkGen)
            .attr('fill', 'none')
            .attr('stroke', '#cbd5e1')
            .attr('stroke-width', 2);

        // Nodes
        const nodes = g.selectAll('.node')
            .data(root.descendants())
            .enter()
            .append('g')
            .attr('class', 'node cursor-pointer')
            .attr('transform', d => `translate(${d.y},${d.x})`)
            .on('click', (event, d) => {
                event.stopPropagation();
                onNodeClick(d.data);
            });

        // Node Rect
        nodes.append('rect')
            .attr('x', 0)
            .attr('y', -30)
            .attr('width', 200)
            .attr('height', 60)
            .attr('rx', 8)
            .attr('fill', d => d.data.group === 'Target' ? '#ecfdf5' : '#f8fafc') // Emerald-50 vs Slate-50
            .attr('stroke', d => d.data.group === 'Target' ? '#10b981' : '#94a3b8')
            .attr('stroke-width', d => d.data.group === 'Target' ? 2 : 1)
            .attr('class', 'transition-all duration-200 hover:filter hover:brightness-95 drop-shadow-sm');

        // Text: Name
        nodes.append('text')
            .attr('dy', -5)
            .attr('x', 15)
            .style('font-weight', '600')
            .style('font-size', '14px')
            .style('fill', '#1e293b') // Slate-800
            .text(d => d.data.label.length > 20 ? d.data.label.substring(0, 18) + '...' : d.data.label);

        // Text: Type / Breeder (Subtitle)
        nodes.append('text')
            .attr('dy', 15)
            .attr('x', 15)
            .style('font-size', '11px')
            .style('fill', '#64748b') // Slate-500
            .text(d => {
                const parts = [];
                if (d.data.type) parts.push(d.data.type);
                if (d.data.breeder) parts.push(d.data.breeder);
                const str = parts.join(' • ');
                return str.length > 28 ? str.substring(0, 26) + '...' : str || 'Unknown Origin';
            });

        // Marker for "Origin" side (Left)
        nodes.append('circle')
            .attr('cx', 0)
            .attr('cy', 0)
            .attr('r', 4)
            .attr('fill', d => d.data.group === 'Target' ? '#10b981' : '#94a3b8');

        // Initial Zoom to Fit
        // A bit manual, standard d3 zoom transform
        const initialTransform = d3.zoomIdentity.translate(100, dimensions.height / 2).scale(0.8);
        svg.call(zoom.transform, initialTransform);

        return () => {
            window.removeEventListener('resize', updateDimensions);
        };
    }, [data, dimensions]);

    return (
        <div ref={wrapperRef} className="w-full h-full bg-slate-50 relative overflow-hidden">
            <div className="absolute top-4 right-4 z-10 opacity-50 pointer-events-none">
                <div className="text-xs text-slate-400 font-mono">SCIENTIFIC MODE</div>
            </div>
            <svg
                ref={svgRef}
                className="w-full h-full"
                style={{ cursor: 'grab' }}
                onMouseDown={(e) => e.currentTarget.style.cursor = 'grabbing'}
                onMouseUp={(e) => e.currentTarget.style.cursor = 'grab'}
            />
        </div>
    );
}
