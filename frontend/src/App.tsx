import React, { useEffect, useMemo, useState } from 'react';
import LazyPlayer, { MediaItem } from './components/LazyPlayer';

interface RawMediaItem extends MediaItem {
  // top-level category
  section: string;
  // second level (may or may not exist)
  pack?: string;
  // you can extend with more categorical keys if needed
}

type Tree = Record<string, Node>;

interface Node {
  children: Tree;
  items: RawMediaItem[];
}

// Utility to safely get nested node creating missing objects
const getOrCreate = (root: Tree, key: string): Node => {
  if (!root[key]) {
    root[key] = { children: {}, items: [] };
  }
  return root[key];
};

const buildTree = (items: RawMediaItem[]): Tree => {
  const root: Tree = {};
  items.forEach((itm) => {
    // Define your hierarchy here – extend as necessary
    const path: string[] = [itm.section];
    if (itm.pack) path.push(itm.pack);

    let current: Node = { children: root, items: [] } as any;
    path.forEach((segment) => {
      current = getOrCreate(current.children, segment);
    });

    current.items.push(itm);
  });
  return root;
};

const formatLabel = (str: string) => str.replace(/_/g, ' ');

const App: React.FC = () => {
  const [tree, setTree] = useState<Tree>({});
  const [path, setPath] = useState<string[]>([]); // navigation stack
  const [search, setSearch] = useState('');
  const [activeUrl, setActiveUrl] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}media_by_section.json`)
      .then((r) => r.json())
      .then((json) => {
        // flatten json (old structure) into RawMediaItem[]
        const list: RawMediaItem[] = [];
        Object.values(json).forEach((arr: any) => {
          list.push(...(arr as RawMediaItem[]));
        });
        setTree(buildTree(list));
      });
  }, []);

  // helper to get current node from path
  const currentNode = useMemo(() => {
    let nodeWrapper: Node | undefined = { children: tree, items: [] } as any;
    for (const segment of path) {
      nodeWrapper = nodeWrapper?.children[segment];
      if (!nodeWrapper) break;
    }
    return nodeWrapper ?? { children: {}, items: [] };
  }, [tree, path]);

  // Reset active player when navigating to a different node
  React.useEffect(() => {
    setActiveUrl('');
  }, [path]);

  // Search filter applies only at leaf where items are shown
  const visibleItems = useMemo(() => {
    return currentNode.items.filter((m) =>
      m.session_title.toLowerCase().includes(search.toLowerCase()),
    );
  }, [currentNode, search]);

  const pauseOthers = (current: HTMLMediaElement) => {
    document.querySelectorAll('audio,video').forEach((el) => {
      if (el !== current) (el as HTMLMediaElement).pause();
    });
  };

  return (
    <div className="flex min-h-screen">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-40 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        style={{background: 'linear-gradient(to bottom, #0ea5e9 0%, #0d9488 100%)'}}
        className={
          `fixed inset-y-0 left-0 w-64 text-gray-100 p-4 space-y-2 overflow-y-auto transform transition-transform duration-200 z-30 ` +
          (sidebarOpen ? 'translate-x-0' : '-translate-x-full') +
          ' md:translate-x-0 md:static md:w-60'
        }
      >
        <h1
          className="text-xl font-bold mb-4 cursor-pointer"
          onClick={() => {
            setPath([]);
            setSidebarOpen(false);
          }}
        >
          MindLive
        </h1>

        {path.length > 0 && (
          <button
            className="block w-full text-left px-2 py-1 mb-2 rounded bg-teal-800 whitespace-normal break-words"
            title="Back"
            onClick={() => setPath((p) => {
              const next = p.slice(0, -1);
              if (next.length === 0) setSidebarOpen(false);
              return next;
            })}
          >
            ← Back
          </button>
        )}

        {Object.keys(currentNode.children).map((key) => (
          <button
            key={key}
            className="block w-full text-left px-2 py-1 rounded hover:bg-teal-800 whitespace-normal break-words"
            title={key}
            onClick={() => {
              const nextPath = [...path, key];
              setPath(nextPath);
              // close drawer only if selected node has no further children
              const childNode = currentNode.children[key];
              if (Object.keys(childNode.children).length === 0) {
                setSidebarOpen(false);
              }
            }}
          >
            {formatLabel(key)}
          </button>
        ))}
      </aside>

      {/* Main Content */}
      <main
        className="flex-1 p-4 md:p-6 overflow-y-auto relative content-area"
      >
        {/* Top bar for mobile */}
        <div className="flex items-center mb-4 md:hidden">
          <button
            className="text-2xl mr-4 text-teal-700"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <span className="font-semibold text-lg">{path[path.length - 1] ? path[path.length - 1].replace(/_/g, ' ') : 'Home'}</span>
        </div>

        {Object.keys(currentNode.children).length === 0 && (
          <input
            type="text"
            placeholder="Search sessions…"
            className="w-full mb-4 p-2 border rounded"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        )}

        {visibleItems.map((item) => (
          <div key={item.cdn_url} className="mb-6 player-card">
            <LazyPlayer
              item={item}
              active={activeUrl === item.cdn_url}
              onActivate={() => setActiveUrl(item.cdn_url)}
            />
          </div>
        ))}
      </main>
    </div>
  );
};

export default App; 