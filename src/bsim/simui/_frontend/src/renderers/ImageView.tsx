import React from 'react'

export default function ImageView({ data }: { data: { src?: string; alt?: string; width?: number; height?: number } }) {
  if (!data?.src) return <div className="empty-state"><p>No image</p></div>
  const { src, alt, width, height } = data
  return (
    <div style={{ overflow: 'auto' }}>
      <img src={src} alt={alt || 'image'} width={width} height={height} style={{ maxWidth: '100%' }} />
    </div>
  )
}
