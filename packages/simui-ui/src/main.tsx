import React from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import '@xyflow/react/dist/style.css'
import './styles/globals.css'

const el = document.getElementById('app')
if (!el) throw new Error('Missing #app root element')
createRoot(el).render(<App />)
