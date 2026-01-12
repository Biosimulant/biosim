import React from 'react'

export default function ImageView({ data, isFullscreen }: { data: { src?: string; alt?: string; width?: number; height?: number }; isFullscreen?: boolean }) {
  if (!data?.src) return <div className="empty-state"><p>No image</p></div>
  const { src, alt, width, height } = data

  if (isFullscreen) {
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'auto' }}>
        <img
          src={src}
          alt={alt || 'image'}
          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
        />
      </div>
    )
  }

  return (
    <div style={{ overflow: 'auto' }}>
      <img src={src} alt={alt || 'image'} width={width} height={height} style={{ maxWidth: '100%' }} />
    </div>
  )
}
