import React, { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Position,
  Handle,
  NodeProps,
  Node,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";
import toast from "react-hot-toast";
import "./MindMapper.css";
import { useStore } from "../../modules/store";
import { NodeTemplate } from "./NodeTemplate";
import { PromptNode } from "./PromptNode";
import { ActionIcon, Button, Menu, TextInput } from "@mantine/core";
import {
  IconMenu2,
  IconPlus,
  IconDownload,
  IconSearch,
  IconPrompt,
  IconCircleDot,
  IconTrash,
  IconCheck,
  IconWorldWww,
} from "@tabler/icons-react";

const nodeDefaults = {
  sourcePosition: Position.Right,
  targetPosition: Position.Left,
};

export type WebsiteReaderNode = Node<
  {
    url?: string;
    onDelete: () => void;
    onChange: (newLabel: string) => void;
  },
  "websiteReaderNode"
>;

const CustomNode = ({ data, id }) => {
  const [label, setLabel] = React.useState(data.label);

  useEffect(() => {
    if (data.isActive) {
      setLabel(data.label);
    }
  }, [data.isActive]);

  useEffect(() => {
    if (data.input) {
      setLabel(data.input);
      toast.success(`Received ${data.input}`, { duration: 500 });
    }
  }, [data.input]);

  return (
    <NodeTemplate data={data}>
      <h3>{data.label}</h3>
      <TextInput
        value={label}
        onChange={(e) => setLabel(e.currentTarget.value)}
        size="xs"
      />
      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
        <Button
          size="xs"
          variant="subtle"
          color="red"
          leftSection={<IconTrash size={14} />}
          onClick={data.onDelete}
        >
          Delete
        </Button>
        <Button
          size="xs"
          leftSection={<IconCheck size={14} />}
          onClick={() => data.onFinish(id, label)}
        >
          Finish
        </Button>
      </div>
    </NodeTemplate>
  );
};

const WebsiteReaderNode = (props: NodeProps<WebsiteReaderNode>) => {
  const [url, setUrl] = useState(props.data.url);

  const fetchWebsite = async (url: string) => {
    toast.loading(`Fetching ${url}`);

    if (!url) return;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.text();

      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = data;
      const textContent = tempDiv.innerText || tempDiv.textContent;

      console.log(textContent);
      toast.dismiss();
      toast.success("Website fetched");
    } catch (error) {
      toast.dismiss();
      console.error("Fetch error:", error);
      toast.error("Failed to fetch website: " + error.message);
    }
  };

  return (
    <NodeTemplate data={props.data} bgColor="var(--hovered-color)">
      <h4>Website Reader</h4>
      <TextInput
        type="url"
        value={url}
        onChange={(e) => setUrl(e.currentTarget.value)}
        placeholder="https://example.com"
        size="xs"
      />
      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
        <Button
          size="xs"
          variant="subtle"
          color="red"
          leftSection={<IconTrash size={14} />}
          onClick={props.data.onDelete}
        >
          Delete
        </Button>
        <Button
          size="xs"
          leftSection={<IconWorldWww size={14} />}
          onClick={() => fetchWebsite(url || "")}
        >
          Fetch
        </Button>
      </div>
    </NodeTemplate>
  );
};

const nodeTypes = {
  customNode: CustomNode,
  websiteReaderNode: WebsiteReaderNode,
  promptNode: PromptNode,
};

const MindMapper = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([] as any[]);

  const [edges, setEdges, onEdgesChange] = useEdgesState([] as any[]);
  const [nodeIdCounter, setNodeIdCounter] = useState(0);

  const { toggleSidebar } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
  }));

  const onConnect = useCallback(
    (params) => setEdges((els) => addEdge(params, els)),
    []
  );

  const onFinish = (nodeId: string, output: any) => {
    const connectedNodes = edges.filter((edge) => edge.source === nodeId);

    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return { ...node, data: { ...node.data, isActive: false } };
        }
        if (connectedNodes.some((edge) => edge.target === node.id)) {
          return {
            ...node,
            data: { ...node.data, isActive: true, inputs: output },
          };
        }
        return node;
      })
    );
  };

  useEffect(() => {
    const initialNodes = [
      {
        id: "1",
        position: { x: 0, y: 150 },
        data: { label: "default style 1", isActive: true },
        type: "promptNode",
        ...nodeDefaults,
      },
      {
        id: "2",
        position: { x: 350, y: 0 },
        data: { label: "default style 2", isActive: false },
        type: "promptNode",
        ...nodeDefaults,
      },
      // {
      //   id: "3",
      //   position: { x: 350, y: 200 },
      //   data: {
      //     label: "default style 3",
      //     // url: "https://www.google.com",
      //     // fetchWebsite: fetchWebsite,
      //     isActive: false,
      //   },
      //   type: "customNode",
      //   ...nodeDefaults,
      // },
    ];

    const initialEdges = [
      {
        id: "e1-2",
        source: "1",
        target: "2",
        animated: true,
      },
      {
        id: "e1-3",
        source: "1",
        target: "3",
        animated: true,
      },
    ];
    setNodes(initialNodes);
    setNodeIdCounter(initialNodes.length + 1);
    setEdges(initialEdges);
  }, []);

  const onNodeChange = useCallback(
    (id, data) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === id) {
            return { ...node, data };
          }
          return node;
        })
      );
    },
    [setNodes]
  );

  const addNode = (type: string) => {
    const newNode = {
      id: `${nodeIdCounter + 1}`,
      position: { x: Math.random() * 500, y: Math.random() * 500 },
      data: { label: `Node ${nodeIdCounter + 1}` },
      type: type,
      ...nodeDefaults,
    };

    setNodes((nds) => nds.concat(newNode));
    setNodeIdCounter(nodeIdCounter + 1);
  };

  const downloadJSON = () => {
    const data = {
      nodes: nodes,
      edges: edges,
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mindmap.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const deleteNode = (id) => {
    setNodes((nds) => nds.filter((node) => node.id !== id));
    setEdges((eds) =>
      eds.filter((edge) => edge.source !== id && edge.target !== id)
    );
  };

  return (
    <div className="mind-mapper">
      <div className="mind-mapper-header">
        <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
          <IconMenu2 size={20} />
        </ActionIcon>

        <Menu position="bottom" withinPortal>
          <Menu.Target>
            <ActionIcon variant="subtle" color="gray">
              <IconPlus size={20} />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item
              leftSection={<IconSearch size={16} />}
              onClick={() => addNode("websiteReaderNode")}
            >
              Website Reader
            </Menu.Item>
            <Menu.Item
              leftSection={<IconCircleDot size={16} />}
              onClick={() => addNode("customNode")}
            >
              Custom Node
            </Menu.Item>
            <Menu.Item
              leftSection={<IconPrompt size={16} />}
              onClick={() => addNode("promptNode")}
            >
              Prompt Node
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>

        <ActionIcon variant="subtle" color="gray" onClick={downloadJSON}>
          <IconDownload size={20} />
        </ActionIcon>
      </div>
      <div className="mind-mapper-canvas">
        <ReactFlow
          nodeTypes={nodeTypes}
          colorMode="dark"
          nodes={nodes.map((node) => ({
            ...node,
            data: {
              ...node.data,
              url: node.data.url || "",
              onDelete: () => deleteNode(node.id),
              onChange: (newData) => onNodeChange(node.id, newData),
              onFinish: (output) => onFinish(node.id, output),
            },
          }))}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
          minZoom={0.1}
          maxZoom={6}
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
    </div>
  );
};

export default MindMapper;
