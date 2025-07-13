import React, { useMemo, useRef } from 'react';
import { usePlyr } from 'plyr-react';
import 'plyr-react/plyr.css';

export interface MediaItem {
  session_title: string;
  media_type: 'audio' | 'video';
  cdn_url: string;
}

interface Props {
  item: MediaItem;
  active: boolean;
  onActivate: () => void;
}

// Internal player rendered **only after** user clicks ▶️
const PlyrPlayer: React.FC<{ itm: MediaItem }> = ({ itm }) => {
  const internalRef = useRef<HTMLMediaElement | null>(null);

  const { source, options } = useMemo(
    () => ({
      source: {
        type: itm.media_type,
        title: itm.session_title,
        sources: [{ src: itm.cdn_url }],
      },
      options: {},
    }),
    [itm],
  );

  // usePlyr returns a ref that needs to be attached to the media element
  const plyrRef = usePlyr(internalRef as any, { source, options });

  return itm.media_type === 'video' ? (
    <video ref={plyrRef as any} className="plyr-react plyr" />
  ) : (
    <audio ref={plyrRef as any} className="plyr-react plyr" />
  );
};

const LazyPlayer: React.FC<Props> = ({ item, active, onActivate }) => {
  if (!active) {
    return (
      <button
        className="play-btn bg-teal-600 text-white px-4 py-2 rounded"
        onClick={onActivate}
      >
        ▶️ {item.session_title}
      </button>
    );
  }

  return (
    <div>
      <div className="font-semibold mb-2 text-gray-800">{item.session_title}</div>
      <PlyrPlayer itm={item} />
    </div>
  );
};

export default LazyPlayer;