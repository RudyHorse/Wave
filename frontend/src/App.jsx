import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import axios from 'axios'
import FileUpload from './components/FileUpload'
import DatabasePanel from './components/DatabasePanel'
import ProcessingPanel from './components/ProcessingPanel'
import ProcessingModal from './components/ProcessingModal'
import Visualization from './components/Visualization'
import SpectrumModal from './components/SpectrumModal'
import AutocorrelationModal from './components/AutocorrelationModal'
import FxSpectrumModal from './components/FxSpectrumModal'
import SnrModal from './components/SnrModal'
import FkSpectrumModal from './components/FkSpectrumModal'

const API_BASE = '/api'

function App() {
  const [fileId, setFileId] = useState(null)
  const [fileName, setFileName] = useState(null)
  const [statistics, setStatistics] = useState(null)
  const [visualizationData, setVisualizationData] = useState(null)
  const [processedData, setProcessedData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [numWindows, setNumWindows] = useState(1)
  const [windows, setWindows] = useState([{ dbFileId: '', fileId: null, data: null, fileName: '' }])
  const [showDifference, setShowDifference] = useState(false)
  const [diffWinA, setDiffWinA] = useState(1)
  const [diffWinB, setDiffWinB] = useState(2)
  const [showDisplay, setShowDisplay] = useState(true)
  const [showDatabase, setShowDatabase] = useState(true)
  const [displayOpen, setDisplayOpen] = useState(false)
  const [windowsOpen, setWindowsOpen] = useState(true)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [sortOpen, setSortOpen] = useState(false)
  const [selectionPanel, setSelectionPanel] = useState(null)
  const [analysisType, setAnalysisType] = useState('spectrum')
  const [dropdownPanel, setDropdownPanel] = useState(null)
  const [spectrumData, setSpectrumData] = useState(null)
  const [autocorrelationData, setAutocorrelationData] = useState(null)
  const [fxSpectrumData, setFxSpectrumData] = useState(null)
const [signalNoiseData, setSignalNoiseData] = useState(null)
const [fkSpectrumData, setFkSpectrumData] = useState(null)
const [spectrumLoading, setSpectrumLoading] = useState(false)
  const [syncView, setSyncView] = useState(null)
  const syncViewRef = useRef(null)
  const [processingSteps, setProcessingSteps] = useState([])
  const abortRef = useRef(null)
  const [colorscale, setColorscale] = useState('Greys')
  const [paletteMin, setPaletteMin] = useState('')
  const [paletteMax, setPaletteMax] = useState('')
  const [amplitudeScale, setAmplitudeScale] = useState(100)
  const [showColorbar, setShowColorbar] = useState(true)
  const [sortMode, setSortMode] = useState('none')
  const [hasInlineXline, setHasInlineXline] = useState(false)
  const [inlineList, setInlineList] = useState([])
  const [selectedInline, setSelectedInline] = useState(null)
  const [inlineTabOffset, setInlineTabOffset] = useState(0)
  const [crosslineList, setCrosslineList] = useState([])
  const [selectedCrossline, setSelectedCrossline] = useState(null)
  const [crosslineTabOffset, setCrosslineTabOffset] = useState(0)
  const [hasCdpOffset, setHasCdpOffset] = useState(false)
  const [cdpList, setCdpList] = useState([])
  const [selectedCdp, setSelectedCdp] = useState(null)
  const [cdpTabOffset, setCdpTabOffset] = useState(0)
  const [hasFfidOffset, setHasFfidOffset] = useState(false)
  const [ffidList, setFfidList] = useState([])
  const [selectedFfid, setSelectedFfid] = useState(null)
  const [ffidTabOffset, setFfidTabOffset] = useState(0)
  const [hasFfidChan, setHasFfidChan] = useState(false)
  const [ffidChanList, setFfidChanList] = useState([])
  const [selectedFfidChan, setSelectedFfidChan] = useState(null)
  const [ffidChanTabOffset, setFfidChanTabOffset] = useState(0)
  const [selectedSample, setSelectedSample] = useState(0)
  const [timeSliceMode, setTimeSliceMode] = useState('scroll')
  const [numGathers, setNumGathers] = useState(1)
  const TABS_VISIBLE = 10
  const [storedFiles, setStoredFiles] = useState([])

  const diffData = useMemo(() => {
    if (numWindows < 2 || !showDifference) return null
    const aIdx = diffWinA - 1
    const bIdx = diffWinB - 1
    const winA = windows[aIdx]?.data
    const winB = windows[bIdx]?.data
    if (!winA || !winB) return null
    if (winA.traces !== winB.traces || winA.samples !== winB.samples) return null
    const data = []
    for (let t = 0; t < winA.traces; t++) {
      const row = []
      for (let s = 0; s < winA.samples; s++) {
        row.push(winA.data[t][s] - winB.data[t][s])
      }
      data.push(row)
    }
    return { ...winA, data }
  }, [windows, showDifference, diffWinA, diffWinB, numWindows])

  const handleViewChange = useCallback((view) => {
    const cur = syncViewRef.current
    if (cur && view &&
      cur.xrange[0] === view.xrange[0] && cur.xrange[1] === view.xrange[1] &&
      cur.yrange[0] === view.yrange[0] && cur.yrange[1] === view.yrange[1]) {
      return
    }
    syncViewRef.current = view
    setSyncView(view)
  }, [])

  const handleUpload = async (file) => {
    setIsLoading(true)
    setError(null)
    setStatistics(null)
    setVisualizationData(null)
    setProcessedData(null)
    setSyncView(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const uploadRes = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      const fid = uploadRes.data.file_id
      setFileId(fid)
      setFileName(uploadRes.data.file_name)

      const [statsRes, vizRes] = await Promise.all([
        axios.get(`${API_BASE}/analyze/${fid}`),
        axios.get(`${API_BASE}/visualize/${fid}`),
      ])

      setStatistics(statsRes.data)
      setVisualizationData(vizRes.data)
      const nv = { xrange: [0, vizRes.data.traces], yrange: [0, vizRes.data.samples] }
      syncViewRef.current = nv
      setSyncView(nv)
      setSortMode('none')
      setSelectedInline(null)
      setInlineList([])
      setInlineTabOffset(0)
      setSelectedCrossline(null)
      setCrosslineList([])
      setCrosslineTabOffset(0)
      setHasCdpOffset(false)
      setCdpList([])
      setSelectedCdp(null)
      setCdpTabOffset(0)
      setHasFfidOffset(false)
      setFfidList([])
      setSelectedFfid(null)
      setFfidTabOffset(0)
      setHasFfidChan(false)
      setFfidChanList([])
      setSelectedFfidChan(null)
      setFfidChanTabOffset(0)
      setSelectedSample(0)
      try {
        const sortRes = await axios.get(`${API_BASE}/sort-info/${fid}`)
        setHasInlineXline(sortRes.data.has_inline_xline)
        setHasCdpOffset(sortRes.data.has_cdp_offset)
        setHasFfidOffset(sortRes.data.has_ffid_offset)
        setHasFfidChan(sortRes.data.has_ffid_chan)
        if (sortRes.data.has_inline_xline) {
          const inlineRes = await axios.get(`${API_BASE}/inline-list/${fid}`)
          setInlineList(inlineRes.data.inlines || [])
        }
        if (sortRes.data.has_crossline_xline) {
          const crosslineRes = await axios.get(`${API_BASE}/crossline-list/${fid}`)
          setCrosslineList(crosslineRes.data.crosslines || [])
        }
        if (sortRes.data.has_cdp_offset) {
          const cdpRes = await axios.get(`${API_BASE}/cdp-list/${fid}`)
          setCdpList(cdpRes.data.cdps || [])
        }
        if (sortRes.data.has_ffid_offset) {
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${fid}`)
          setFfidList(ffidRes.data.ffids || [])
        }
        if (sortRes.data.has_ffid_chan) {
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${fid}`)
          setFfidChanList(ffidRes.data.ffids || [])
        }
      } catch (e) {
        setHasInlineXline(false)
      }
      setSuccessMessage('Load complete')
      setTimeout(() => setSuccessMessage(null), 2500)
      fetchStoredFiles()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process file')
      setFileId(null)
      setFileName(null)
    } finally {
      setIsLoading(false)
    }
  }

  const handleRunProcessing = async (steps, parallel, numWorkers, inputFileId, outputName, dsinConfig, inputSortConfig) => {
    if (!fileId && !inputFileId && !dsinConfig) return
    setProcessingSteps(steps)
    setIsProcessing(true)
    setError(null)

    const controller = new AbortController()
    abortRef.current = controller

    let activeFileId = fileId

    try {
      if (dsinConfig) {
        const dsinRes = await axios.post(`${API_BASE}/dsin`, dsinConfig)
        activeFileId = dsinRes.data.file_id
        setFileId(activeFileId)
        setFileName(dsinRes.data.file_name)
        setStatistics(dsinRes.data.statistics)
        setVisualizationData(dsinRes.data.visualization)
        setProcessedData(null)
        const nv = { xrange: [0, dsinRes.data.visualization.traces], yrange: [0, dsinRes.data.visualization.samples] }
        syncViewRef.current = nv
        setSyncView(nv)
        setSuccessMessage(`Loaded ${dsinRes.data.file_name}`)
        setTimeout(() => setSuccessMessage(null), 2500)
      } else if (inputFileId) {
        const loadRes = await axios.post(`${API_BASE}/load-from-db`, { file_id: inputFileId, ...(inputSortConfig || {}) })
        activeFileId = loadRes.data.file_id
        setFileId(activeFileId)
        setFileName(loadRes.data.file_name)
        setStatistics(loadRes.data.statistics)
        setVisualizationData(loadRes.data.visualization)
        setProcessedData(null)
        const nv = { xrange: [0, loadRes.data.visualization.traces], yrange: [0, loadRes.data.visualization.samples] }
        syncViewRef.current = nv
        setSyncView(nv)
      }

      if (steps.length > 0) {
        const runRes = await axios.post(`${API_BASE}/process/run/${activeFileId}`, { steps, parallel: parallel || false, num_workers: numWorkers || 4 }, { signal: controller.signal })
        const hasSignalSteps = steps.some(s => s.type !== 'dsout')
        if (hasSignalSteps) {
          const vizRes = await axios.get(`${API_BASE}/visualize/processed/${activeFileId}`)
          setProcessedData(vizRes.data)
          if (!syncView) {
            const nv = { xrange: [0, vizRes.data.traces], yrange: [0, vizRes.data.samples] }
            syncViewRef.current = nv
            setSyncView(nv)
          }
        }

        const dsoutResults = runRes.data?.dsout || []
        if (dsoutResults.length > 0) {
          setSuccessMessage(`Saved ${dsoutResults[0].traces} traces to ${dsoutResults[0].path}`)
          setTimeout(() => setSuccessMessage(null), 4000)
        }
      }

      if (outputName) {
        await axios.post(`${API_BASE}/save-to-db/${activeFileId}`, { name: outputName })
        setSuccessMessage(`Saved "${outputName}" to DB`)
        setTimeout(() => setSuccessMessage(null), 2500)
        fetchStoredFiles()
      }
    } catch (err) {
      if (axios.isCancel(err)) return
      if (err.response?.status === 409) return
      setError(err.response?.data?.detail || 'Processing failed')
    } finally {
      setIsProcessing(false)
      setProcessingSteps([])
      abortRef.current = null
    }
  }

  const handleWindowFileSelect = async (winIndex, dbFileId) => {
    if (!dbFileId) {
      const newWindows = [...windows]
      newWindows[winIndex] = { dbFileId: '', fileId: null, data: null, fileName: '' }
      setWindows(newWindows)
      return
    }
    try {
      const res = await axios.post(`${API_BASE}/load-from-db`, { file_id: dbFileId })
      const fileId_ = res.data.file_id
      const stats = res.data.statistics
      const hasInline = !!(stats.inline_min || stats.inline_max)
      let inlineVal = selectedInline
      let crosslineVal = selectedCrossline
      let cdpVal = selectedCdp
      let ffidVal = selectedFfid
      if (hasInline) {
        setHasInlineXline(true)
        try {
          const [inlineRes, crosslineRes] = await Promise.all([
            axios.get(`${API_BASE}/inline-list/${fileId_}`),
            axios.get(`${API_BASE}/crossline-list/${fileId_}`),
          ])
          const inlines = inlineRes.data.inlines || []
          const crosslines = crosslineRes.data.crosslines || []
          setInlineList(inlines)
          setCrosslineList(crosslines)
          if (sortMode === 'inline_xline' && inlines.length > 0) {
            inlineVal = inlines[0]
            setSelectedInline(inlineVal)
          }
          if (sortMode === 'crossline_xline' && crosslines.length > 0) {
            crosslineVal = crosslines[0]
            setSelectedCrossline(crosslineVal)
          }
        } catch (e) {}
      }
      try {
        const sortRes = await axios.get(`${API_BASE}/sort-info/${fileId_}`)
        if (sortRes.data.has_cdp_offset) {
          setHasCdpOffset(true)
          const cdpRes = await axios.get(`${API_BASE}/cdp-list/${fileId_}`)
          const cdps = cdpRes.data.cdps || []
          setCdpList(cdps)
          if (sortMode === 'cdp_offset' && cdps.length > 0) {
            cdpVal = cdps[0]
            setSelectedCdp(cdpVal)
          }
        }
        if (sortRes.data.has_ffid_chan) {
          setHasFfidChan(true)
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${fileId_}`)
          const ffids = ffidRes.data.ffids || []
          setFfidChanList(ffids)
          if (sortMode === 'ffid_chan' && ffids.length > 0) {
            ffidVal = ffids[0]
            setSelectedFfidChan(ffidVal)
          }
        } else {
          setHasFfidChan(false)
          setFfidChanList([])
          setSelectedFfidChan(null)
        }
      } catch (e) {}
      try {
        const sortRes2 = await axios.get(`${API_BASE}/sort-info/${fileId_}`)
        if (sortRes2.data.has_ffid_offset) {
          setHasFfidOffset(true)
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${fileId_}`)
          const ffids = ffidRes.data.ffids || []
          setFfidList(ffids)
          if (sortMode === 'ffid_offset' && ffids.length > 0) {
            ffidVal = ffids[0]
            setSelectedFfid(ffidVal)
          }
        } else {
          setHasFfidOffset(false)
          setFfidList([])
          setSelectedFfid(null)
        }
        if (sortRes2.data.has_ffid_chan) {
          setHasFfidChan(true)
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${fileId_}`)
          const ffids = ffidRes.data.ffids || []
          setFfidChanList(ffids)
          if (sortMode === 'ffid_chan' && ffids.length > 0) {
            ffidVal = ffids[0]
            setSelectedFfidChan(ffidVal)
          }
        } else {
          setHasFfidChan(false)
          setFfidChanList([])
          setSelectedFfidChan(null)
        }
      } catch (e) {}
      const params = { sort_mode: sortMode, num_gathers: numGathers }
      if (sortMode === 'inline_xline' && inlineVal != null) params.inline = inlineVal
      if (sortMode === 'crossline_xline' && crosslineVal != null) params.crossline = crosslineVal
      if (sortMode === 'cdp_offset' && cdpVal != null) params.inline = cdpVal
      if (sortMode === 'ffid_offset' && ffidVal != null) params.inline = ffidVal
      if (sortMode === 'ffid_chan' && ffidVal != null) params.inline = ffidVal
      let vizData = res.data.visualization
      if (sortMode !== 'none') {
        try {
          const vizRes = await axios.get(`${API_BASE}/visualize/${fileId_}`, { params })
          vizData = vizRes.data
        } catch (e) {}
      }
      const newWindows = [...windows]
      newWindows[winIndex] = {
        dbFileId,
        fileId: fileId_,
        data: vizData,
        fileName: res.data.file_name.replace(/\.sgy$/i, '')
      }
      setWindows(newWindows)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load file for display')
    }
  }

  const handleNumWindowsChange = (n) => {
    const count = Math.max(1, Math.min(4, n))
    setNumWindows(count)
    setWindows(prev => {
      if (prev.length < count) {
        return [...prev, ...Array(count - prev.length).fill({}).map(() => ({ dbFileId: '', fileId: null, data: null, fileName: '' }))]
      }
      return prev.slice(0, count)
    })
    setDiffWinA(1)
    setDiffWinB(count >= 2 ? 2 : 1)
  }

  const handleCancelProcessing = async () => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    if (fileId) {
      try {
        await axios.post(`${API_BASE}/process/cancel/${fileId}`)
      } catch (e) {
      }
    }
    setIsProcessing(false)
    setProcessingSteps([])
    setProcessedData(null)
    setError(null)
  }

  const handleSelection = async (range, clickedWinIdx) => {
    if (spectrumLoading) return

    const clickedData = windows[clickedWinIdx]?.data
    if (!clickedData) return

    setSpectrumLoading(true)

    const traceStart = Math.floor(range.trace_start * (clickedData.trace_step || 1))
    const traceEnd = Math.ceil(range.trace_end * (clickedData.trace_step || 1))
    const sampleStart = Math.floor(range.sample_start * (clickedData.sample_step || 1))
    const sampleEnd = Math.ceil(range.sample_end * (clickedData.sample_step || 1))

  const endpoint = analysisType === 'autocorrelation' ? 'autocorrelation'
    : analysisType === 'fxspectrum' ? 'fx-spectrum'
    : analysisType === 'signalnoise' ? 'signal-noise'
    : analysisType === 'fkspectrum' ? 'fk-spectrum'
    : 'spectrum'

    try {
      const results = await Promise.all(
        windows.map(async (win, i) => {
          if (!win?.fileId || !win?.data) return null
          const res = await axios.post(`${API_BASE}/${endpoint}/${win.fileId}`, {
            trace_start: traceStart, trace_end: traceEnd,
            sample_start: sampleStart, sample_end: sampleEnd,
            use_processed: false,
          })
          return { label: `Win ${i + 1}: ${win.fileName || ''}`, ...res.data }
        })
      )
      const filtered = results.filter(Boolean)
      if (filtered.length === 0) return
    if (analysisType === 'autocorrelation') setAutocorrelationData(filtered)
    else if (analysisType === 'fxspectrum') setFxSpectrumData(filtered)
    else if (analysisType === 'signalnoise') setSignalNoiseData(filtered)
    else if (analysisType === 'fkspectrum') setFkSpectrumData(filtered)
    else setSpectrumData(filtered)
      setSelectionPanel(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Analysis failed')
    } finally {
      setSpectrumLoading(false)
    }
  }

  const fetchStoredFiles = async () => {
    try {
      const res = await axios.get(`${API_BASE}/stored-files`)
      setStoredFiles(res.data || [])
    } catch (e) {
      console.error('fetchStoredFiles error:', e)
    }
  }

  const handleLoadFromDb = async (dbFileId) => {
    try {
      const res = await axios.post(`${API_BASE}/load-from-db`, { file_id: dbFileId })
      const { file_id, statistics, visualization, file_name } = res.data
      setFileId(file_id)
      setFileName(file_name)
      setStatistics(statistics)
      setVisualizationData(visualization)
      setProcessedData(null)
      const nv = { xrange: [0, visualization.traces], yrange: [0, visualization.samples] }
      syncViewRef.current = nv
      setSyncView(nv)
      setHasInlineXline(!!(statistics.inline_min || statistics.inline_max))
      setHasCdpOffset(false)
      setCdpList([])
      setSelectedCdp(null)
      setHasFfidOffset(false)
      setFfidList([])
      setSelectedFfid(null)
      setHasFfidChan(false)
      setFfidChanList([])
      setSelectedFfidChan(null)
      try {
        const sortRes = await axios.get(`${API_BASE}/sort-info/${file_id}`)
        if (sortRes.data.has_cdp_offset) {
          setHasCdpOffset(true)
          const cdpRes = await axios.get(`${API_BASE}/cdp-list/${file_id}`)
          setCdpList(cdpRes.data.cdps || [])
        }
        if (sortRes.data.has_ffid_offset) {
          setHasFfidOffset(true)
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${file_id}`)
          setFfidList(ffidRes.data.ffids || [])
        }
        if (sortRes.data.has_ffid_chan) {
          setHasFfidChan(true)
          const ffidRes = await axios.get(`${API_BASE}/ffid-list/${file_id}`)
          setFfidChanList(ffidRes.data.ffids || [])
        }
      } catch (e) {}
      setSuccessMessage(`Loaded ${file_name}`)
      setTimeout(() => setSuccessMessage(null), 2500)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load file from DB')
    }
  }

  const handleRemoveFromDb = async (dbFileId) => {
    try {
      await axios.delete(`${API_BASE}/files/${dbFileId}`)
      fetchStoredFiles()
      if (fileId === dbFileId) {
        setFileId(null)
        setFileName(null)
        setStatistics(null)
        setVisualizationData(null)
        setProcessedData(null)
        setWindows([{ dbFileId: '', fileId: null, data: null, fileName: '' }])
        setNumWindows(1)
        setShowDifference(false)
        setDiffWinA(1)
        setDiffWinB(2)
      }
    } catch (e) {}
  }

  const handleSaveToDb = async (name) => {
    if (!fileId) return
    try {
      await axios.post(`${API_BASE}/save-to-db/${fileId}`, { name })
      setSuccessMessage(`Saved "${name}" to DB`)
      setTimeout(() => setSuccessMessage(null), 2500)
      fetchStoredFiles()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save to DB')
    }
  }

  const refreshWindowVisualization = async (sort, lineVal) => {
    const params = { sort_mode: sort, num_gathers: numGathers }
    if (sort === 'inline_xline' && lineVal != null) params.inline = lineVal
    if (sort === 'crossline_xline' && lineVal != null) params.crossline = lineVal
    if (sort === 'cdp_offset' && lineVal != null) params.inline = lineVal
    if (sort === 'ffid_offset' && lineVal != null) params.inline = lineVal
    if (sort === 'ffid_chan' && lineVal != null) params.inline = lineVal
    const newWindows = await Promise.all(windows.map(async (win) => {
      if (!win.fileId) return win
      try {
        const res = await axios.get(`${API_BASE}/visualize/${win.fileId}`, { params })
        return { ...win, data: res.data }
      } catch (e) {
        return win
      }
    }))
    setWindows(newWindows)
  }

  const fetchVisualization = async (sort, lineVal) => {
    const params = { sort_mode: sort, num_gathers: numGathers }
    if (sort === 'inline_xline' && lineVal != null) params.inline = lineVal
    if (sort === 'crossline_xline' && lineVal != null) params.crossline = lineVal
    if (sort === 'cdp_offset' && lineVal != null) params.inline = lineVal
    if (sort === 'ffid_offset' && lineVal != null) params.inline = lineVal
    if (sort === 'ffid_chan' && lineVal != null) params.inline = lineVal
    if (fileId) {
      try {
        const vizRes = await axios.get(`${API_BASE}/visualize/${fileId}`, { params })
        setVisualizationData(vizRes.data)
        const nv = { xrange: [0, vizRes.data.traces], yrange: [0, vizRes.data.samples] }
        syncViewRef.current = nv
        setSyncView(nv)
        if (processedData) {
          try {
            const procRes = await axios.get(`${API_BASE}/visualize/processed/${fileId}`, { params })
            setProcessedData(procRes.data)
          } catch (e) {}
        }
      } catch (e) {}
    }
    await refreshWindowVisualization(sort, lineVal)
  }

  const handleSortModeChange = async (newMode) => {
    setSortMode(newMode)
    if (newMode === 'inline_xline' && inlineList.length > 0) {
      setSelectedInline(inlineList[0])
      await fetchVisualization(newMode, inlineList[0])
    } else if (newMode === 'crossline_xline' && crosslineList.length > 0) {
      setSelectedCrossline(crosslineList[0])
      await fetchVisualization(newMode, crosslineList[0])
    } else if (newMode === 'cdp_offset' && cdpList.length > 0) {
      setSelectedCdp(cdpList[0])
      await fetchVisualization(newMode, cdpList[0])
    } else if (newMode === 'ffid_offset' && ffidList.length > 0) {
      setSelectedFfid(ffidList[0])
      await fetchVisualization(newMode, ffidList[0])
    } else if (newMode === 'ffid_chan' && ffidChanList.length > 0) {
      setSelectedFfidChan(ffidChanList[0])
      await fetchVisualization(newMode, ffidChanList[0])
    } else if (newMode === 'time_slice') {
      await fetchTimeSlice(selectedSample)
    } else {
      setSelectedInline(null)
      setSelectedCrossline(null)
      setSelectedCdp(null)
      setSelectedFfid(null)
      setSelectedFfidChan(null)
      await fetchVisualization(newMode, null)
    }
  }

  const fetchTimeSlice = async (sample) => {
    const newWindows = await Promise.all(windows.map(async (win) => {
      if (!win.fileId) return win
      try {
        const res = await axios.get(`${API_BASE}/time-slice/${win.fileId}`, { params: { sample } })
        return { ...win, data: res.data }
      } catch (e) {
        return win
      }
    }))
    setWindows(newWindows)
    if (fileId) {
      try {
        const res = await axios.get(`${API_BASE}/time-slice/${fileId}`, { params: { sample } })
        setVisualizationData(res.data)
      } catch (e) {}
    }
  }

  const handleSampleChange = async (sample) => {
    setSelectedSample(sample)
    await fetchTimeSlice(sample)
  }

  const handleInlineChange = async (il) => {
    setSelectedInline(il)
    setInlineTabOffset(Math.min(Math.max(0, inlineList.indexOf(il) - Math.floor(TABS_VISIBLE / 2)), Math.max(0, inlineList.length - TABS_VISIBLE)))
    await fetchVisualization('inline_xline', il)
  }

  const handleCrosslineChange = async (xl) => {
    setSelectedCrossline(xl)
    setCrosslineTabOffset(Math.min(Math.max(0, crosslineList.indexOf(xl) - Math.floor(TABS_VISIBLE / 2)), Math.max(0, crosslineList.length - TABS_VISIBLE)))
    await fetchVisualization('crossline_xline', xl)
  }

  const handleCdpChange = async (cdp) => {
    setSelectedCdp(cdp)
    setCdpTabOffset(Math.min(Math.max(0, cdpList.indexOf(cdp) - Math.floor(TABS_VISIBLE / 2)), Math.max(0, cdpList.length - TABS_VISIBLE)))
    await fetchVisualization('cdp_offset', cdp)
  }

  const handleFfidChange = async (ffid) => {
    setSelectedFfid(ffid)
    setFfidTabOffset(Math.min(Math.max(0, ffidList.indexOf(ffid) - Math.floor(TABS_VISIBLE / 2)), Math.max(0, ffidList.length - TABS_VISIBLE)))
    await fetchVisualization('ffid_offset', ffid)
  }

  const handleFfidChanChange = async (ffid) => {
    setSelectedFfidChan(ffid)
    setFfidChanTabOffset(Math.min(Math.max(0, ffidChanList.indexOf(ffid) - Math.floor(TABS_VISIBLE / 2)), Math.max(0, ffidChanList.length - TABS_VISIBLE)))
    await fetchVisualization('ffid_chan', ffid)
  }

  useEffect(() => {
    fetchStoredFiles()
  }, [])

  useEffect(() => {
    const onKeyDown = (e) => {
      if (sortMode === 'inline_xline' && selectedInline != null && inlineList.length > 0) {
        const idx = inlineList.indexOf(selectedInline)
        if (e.key === 'ArrowLeft' && idx > 0) {
          handleInlineChange(inlineList[idx - 1])
        } else if (e.key === 'ArrowRight' && idx < inlineList.length - 1) {
          handleInlineChange(inlineList[idx + 1])
        }
      } else if (sortMode === 'crossline_xline' && selectedCrossline != null && crosslineList.length > 0) {
        const idx = crosslineList.indexOf(selectedCrossline)
        if (e.key === 'ArrowLeft' && idx > 0) {
          handleCrosslineChange(crosslineList[idx - 1])
        } else if (e.key === 'ArrowRight' && idx < crosslineList.length - 1) {
          handleCrosslineChange(crosslineList[idx + 1])
        }
      } else if (sortMode === 'cdp_offset' && selectedCdp != null && cdpList.length > 0) {
        const idx = cdpList.indexOf(selectedCdp)
        if (e.key === 'ArrowLeft' && idx > 0) {
          handleCdpChange(cdpList[idx - 1])
        } else if (e.key === 'ArrowRight' && idx < cdpList.length - 1) {
          handleCdpChange(cdpList[idx + 1])
        }
      } else if (sortMode === 'ffid_offset' && selectedFfid != null && ffidList.length > 0) {
        const idx = ffidList.indexOf(selectedFfid)
        if (e.key === 'ArrowLeft' && idx > 0) {
          handleFfidChange(ffidList[idx - 1])
        } else if (e.key === 'ArrowRight' && idx < ffidList.length - 1) {
          handleFfidChange(ffidList[idx + 1])
        }
      } else if (sortMode === 'ffid_chan' && selectedFfidChan != null && ffidChanList.length > 0) {
        const idx = ffidChanList.indexOf(selectedFfidChan)
        if (e.key === 'ArrowLeft' && idx > 0) {
          handleFfidChanChange(ffidChanList[idx - 1])
        } else if (e.key === 'ArrowRight' && idx < ffidChanList.length - 1) {
          handleFfidChanChange(ffidChanList[idx + 1])
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  const handleYRangeChange = (start, end) => {
    const cur = syncViewRef.current
    if (cur && cur.yrange[0] === start && cur.yrange[1] === end) return
    const nv = {
      xrange: cur?.xrange || [0, visualizationData?.traces || 500],
      yrange: [start, end],
    }
    syncViewRef.current = nv
    setSyncView(nv)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>
          <svg className="header-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 12h2m4 0h2m4 0h2m4 0h2M4 8v8m4-8v8m4-8v8m4-8v8" />
          </svg>
          Wave 0.0
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            className="btn-fullscreen"
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? 'Show sidebar' : 'Fullscreen visualization'}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {isFullscreen
                ? <><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" /></>
                : <><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" /></>
              }
            </svg>
          </button>
          <div className="status-indicator">
            <span className="status-dot"></span>
            <span>Ready</span>
          </div>
        </div>
      </header>

      <main className={`app-main ${isFullscreen ? 'fullscreen' : ''}`}>
        <aside className={`sidebar ${isFullscreen ? 'hidden' : ''}`}>
          <FileUpload
            onUpload={handleUpload}
            isLoading={isLoading}
          />

          {error && (
            <div className="error-message">{error}</div>
          )}

          <DatabasePanel storedFiles={storedFiles} showDatabase={showDatabase} onToggle={setShowDatabase} />

          <ProcessingPanel
            fileId={fileId}
            onRun={(steps, parallel, numWorkers, inputFileId, outputName, dsinConfig, inputSortConfig) => handleRunProcessing(steps, parallel, numWorkers, inputFileId, outputName, dsinConfig, inputSortConfig)}
            isRunning={isProcessing}
            storedFiles={storedFiles}
          />

          <div className="card">
            <div className="card-header" style={{ cursor: 'default', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }} onClick={() => setDisplayOpen(!displayOpen)}>
                <span className={`collapse-icon ${displayOpen ? '' : 'collapsed'}`}>&#9660;</span>
                <span>Display</span>
              </div>
              <label className="toggle-switch" onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" checked={showDisplay} onChange={(e) => setShowDisplay(e.target.checked)} />
                <span className="toggle-slider"></span>
              </label>
            </div>
            {displayOpen && (
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div className="subblock">
                <div className="subblock-header" onClick={() => setWindowsOpen(!windowsOpen)}>
                  <span className={`collapse-icon ${windowsOpen ? '' : 'collapsed'}`}>&#9660;</span>
                  <span className="subblock-title">Windows</span>
                </div>
                {windowsOpen && (
                <div className="subblock-body">
                  <div className="param-row">
                    <span className="param-label">Windows</span>
                    <input className="param-input" type="number" min="1" max="4" step="1"
                      value={numWindows}
                      onChange={(e) => handleNumWindowsChange(Number(e.target.value))}
                      style={{ width: '50px' }} />
                  </div>
                  {Array.from({ length: numWindows }, (_, i) => (
                    <div key={i} className="window-source-row">
                      <span className="window-source-label">Win {i + 1}</span>
                      <select className="param-select" style={{ flex: 1, fontSize: '10px' }}
                        value={windows[i]?.dbFileId || ''}
                        onChange={(e) => handleWindowFileSelect(i, e.target.value)}>
                        <option value="">-- Select --</option>
                        {(storedFiles || []).map((f) => (
                          <option key={f.id} value={f.id}>{f.name.replace(/\.sgy$/i, '')}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                  {numWindows > 1 && (
                    <label className="toggle-row" style={{ fontSize: '12px' }}>
                      <span>Difference</span>
                      <label className="toggle-switch">
                        <input type="checkbox" checked={showDifference} onChange={(e) => setShowDifference(e.target.checked)} />
                        <span className="toggle-slider"></span>
                      </label>
                    </label>
                  )}
                  {numWindows > 2 && showDifference && (
                    <div className="diff-select-row">
                      <span className="param-label">Diff</span>
                      <select className="param-select" style={{ width: '48px', fontSize: '10px' }}
                        value={diffWinA} onChange={(e) => setDiffWinA(Number(e.target.value))}>
                        {Array.from({ length: numWindows }, (_, i) => (
                          <option key={i} value={i + 1}>W{i + 1}</option>
                        ))}
                      </select>
                      <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>−</span>
                      <select className="param-select" style={{ width: '48px', fontSize: '10px' }}
                        value={diffWinB} onChange={(e) => setDiffWinB(Number(e.target.value))}>
                        {Array.from({ length: numWindows }, (_, i) => (
                          <option key={i} value={i + 1}>W{i + 1}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
                )}
              </div>
              <div className="subblock">
                <div className="subblock-header" onClick={() => setSortOpen(!sortOpen)}>
                  <span className={`collapse-icon ${sortOpen ? '' : 'collapsed'}`}>&#9660;</span>
                  <span className="subblock-title">Sort</span>
                </div>
                {sortOpen && (
                <div className="subblock-body">
                  <div className="param-row">
                    <span className="param-label">Sort</span>
                    <select className="param-select" value={sortMode} onChange={(e) => handleSortModeChange(e.target.value)} disabled={!hasInlineXline}>
                      <option value="none">None</option>
                      <option value="inline_xline">Inline / Xline</option>
                      <option value="crossline_xline">Xline / Inline</option>
                      <option value="cdp_offset">CDP / Offset</option>
                      <option value="ffid_offset">FFID / Offset</option>
                      <option value="ffid_chan">FFID / Chan</option>
                      <option value="time_slice">Time Slice</option>
                    </select>
                  </div>
                  {sortMode !== 'time_slice' && sortMode !== 'none' && (
                    <div className="param-row">
                      <span className="param-label">Gathers</span>
                      <input className="param-input" type="number" min="1" max="100" style={{ width: '60px' }}
                        value={numGathers}
                        onChange={(e) => {
                          const v = Math.max(1, Number(e.target.value))
                          setNumGathers(v)
                          if (sortMode === 'inline_xline' && selectedInline != null) fetchVisualization(sortMode, selectedInline)
                          else if (sortMode === 'crossline_xline' && selectedCrossline != null) fetchVisualization(sortMode, selectedCrossline)
                          else if (sortMode === 'cdp_offset' && selectedCdp != null) fetchVisualization(sortMode, selectedCdp)
                          else if (sortMode === 'ffid_offset' && selectedFfid != null) fetchVisualization(sortMode, selectedFfid)
                          else if (sortMode === 'ffid_chan' && selectedFfidChan != null) fetchVisualization(sortMode, selectedFfidChan)
                        }} />
                    </div>
                  )}
                  {sortMode === 'time_slice' && (statistics?.samples_per_trace || windows.some(w => w.data?.samples_original)) && (
                    <div className="param-row">
                      <span className="param-label">Slice</span>
                      <select className="param-select" value={timeSliceMode} onChange={(e) => setTimeSliceMode(e.target.value)}>
                        <option value="scroll">Scroll</option>
                        <option value="exact">Exact</option>
                      </select>
                    </div>
                  )}
                  {(() => {
                    const maxS = statistics?.samples_per_trace
                      || (windows.find(w => w.data?.samples_original)?.data?.samples_original)
                      || 0
                    if (maxS < 1) return null
                    return sortMode === 'time_slice' && timeSliceMode === 'scroll' ? (
                      <div className="param-row">
                        <input className="param-input" type="range" min="0" max={maxS - 1}
                          value={Math.min(selectedSample, maxS - 1)}
                          onChange={(e) => handleSampleChange(Number(e.target.value))}
                          style={{ flex: 1 }} />
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', minWidth: '60px', textAlign: 'right' }}>{selectedSample}</span>
                      </div>
                    ) : null
                  })()}
                  {(() => {
                    const maxS = statistics?.samples_per_trace
                      || (windows.find(w => w.data?.samples_original)?.data?.samples_original)
                      || 0
                    if (maxS < 1) return null
                    return sortMode === 'time_slice' && timeSliceMode === 'exact' ? (
                      <div className="param-row">
                        <span className="param-label">Sample</span>
                        <input className="param-input" type="number" min="0" max={maxS - 1} style={{ width: '80px' }}
                          value={selectedSample}
                          onChange={(e) => handleSampleChange(Number(e.target.value))} />
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)' }}>/ {maxS - 1}</span>
                      </div>
                    ) : null
                  })()}
                  {(sortMode === 'inline_xline' || sortMode === 'crossline_xline' || sortMode === 'cdp_offset' || sortMode === 'ffid_offset' || sortMode === 'ffid_chan') && (
                    <div className="param-row">
                      <span className="param-label">Go to</span>
                      <input className="param-input" type="number" style={{ width: '100px' }}
                        placeholder={sortMode === 'inline_xline' ? 'Inline' : sortMode === 'crossline_xline' ? 'Xline' : sortMode === 'cdp_offset' ? 'CDP' : sortMode === 'ffid_chan' ? 'FFID' : 'FFID'}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const val = Number(e.target.value)
                            const list = sortMode === 'inline_xline' ? inlineList : sortMode === 'crossline_xline' ? crosslineList : sortMode === 'cdp_offset' ? cdpList : sortMode === 'ffid_chan' ? ffidChanList : ffidList
                            const change = sortMode === 'inline_xline' ? handleInlineChange : sortMode === 'crossline_xline' ? handleCrosslineChange : sortMode === 'cdp_offset' ? handleCdpChange : sortMode === 'ffid_chan' ? handleFfidChanChange : handleFfidChange
                            if (list.includes(val)) {
                              change(val)
                            } else if (list.length > 0) {
                              const closest = list.reduce((a, b) => Math.abs(a - val) < Math.abs(b - val) ? a : b)
                              change(closest)
                            }
                          }
                        }} />
                    </div>
                  )}
                  {sortMode === 'inline_xline' && inlineList.length > 0 && (
                    <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setInlineTabOffset(Math.max(0, inlineTabOffset - TABS_VISIBLE))}
                        style={{ opacity: inlineTabOffset > 0 ? 1 : 0.3, cursor: inlineTabOffset > 0 ? 'pointer' : 'default' }}
                      >&#9664;</span>
                      <div className="mode-selector inline-tabs" style={{ flex: 1 }}>
                        {inlineList.slice(inlineTabOffset, inlineTabOffset + TABS_VISIBLE).map((il) => (
                          <span
                            key={il}
                            className={`mode-option${selectedInline === il ? ' active' : ''}`}
                            onClick={() => handleInlineChange(il)}
                            style={{ fontSize: '10px', padding: '2px 4px' }}
                          >
                            {il}
                          </span>
                        ))}
                      </div>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setInlineTabOffset(Math.min(inlineList.length - TABS_VISIBLE, inlineTabOffset + TABS_VISIBLE))}
                        style={{ opacity: inlineTabOffset + TABS_VISIBLE < inlineList.length ? 1 : 0.3, cursor: inlineTabOffset + TABS_VISIBLE < inlineList.length ? 'pointer' : 'default' }}
                      >&#9654;</span>
                    </div>
                  )}
                  {sortMode === 'inline_xline' && inlineList.length > 0 && (
                    <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = inlineList.indexOf(selectedInline)
                          if (curIdx > 0) {
                            const step = Math.max(0, curIdx - 10)
                            handleInlineChange(inlineList[step])
                          }
                        }}
                        style={{ opacity: inlineList.indexOf(selectedInline) > 0 ? 1 : 0.3, cursor: inlineList.indexOf(selectedInline) > 0 ? 'pointer' : 'default', fontSize: '11px' }}
                      >◀◀</span>
                      <span style={{ color: '#8b949e', fontSize: '10px' }}>
                        Step: {inlineList.indexOf(selectedInline) + 1} / {inlineList.length}
                      </span>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = inlineList.indexOf(selectedInline)
                          if (curIdx < inlineList.length - 1) {
                            const step = Math.min(inlineList.length - 1, curIdx + 10)
                            handleInlineChange(inlineList[step])
                          }
                        }}
                        style={{ opacity: inlineList.indexOf(selectedInline) < inlineList.length - 1 ? 1 : 0.3, cursor: inlineList.indexOf(selectedInline) < inlineList.length - 1 ? 'pointer' : 'default', fontSize: '11px' }}
                      >▶▶</span>
                    </div>
                  )}
                  {sortMode === 'crossline_xline' && crosslineList.length > 0 && (
                    <>
                    <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setCrosslineTabOffset(Math.max(0, crosslineTabOffset - TABS_VISIBLE))}
                        style={{ opacity: crosslineTabOffset > 0 ? 1 : 0.3, cursor: crosslineTabOffset > 0 ? 'pointer' : 'default' }}
                      >&#9664;</span>
                      <div className="mode-selector inline-tabs" style={{ flex: 1 }}>
                        {crosslineList.slice(crosslineTabOffset, crosslineTabOffset + TABS_VISIBLE).map((xl) => (
                          <span
                            key={xl}
                            className={`mode-option${selectedCrossline === xl ? ' active' : ''}`}
                            onClick={() => handleCrosslineChange(xl)}
                            style={{ fontSize: '10px', padding: '2px 4px' }}
                          >
                            {xl}
                          </span>
                        ))}
                      </div>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setCrosslineTabOffset(Math.min(crosslineList.length - TABS_VISIBLE, crosslineTabOffset + TABS_VISIBLE))}
                        style={{ opacity: crosslineTabOffset + TABS_VISIBLE < crosslineList.length ? 1 : 0.3, cursor: crosslineTabOffset + TABS_VISIBLE < crosslineList.length ? 'pointer' : 'default' }}
                      >&#9654;</span>
                    </div>
                    <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = crosslineList.indexOf(selectedCrossline)
                          if (curIdx > 0) {
                            const step = Math.max(0, curIdx - 10)
                            handleCrosslineChange(crosslineList[step])
                          }
                        }}
                        style={{ opacity: crosslineList.indexOf(selectedCrossline) > 0 ? 1 : 0.3, cursor: crosslineList.indexOf(selectedCrossline) > 0 ? 'pointer' : 'default', fontSize: '11px' }}
                      >◀◀</span>
                      <span style={{ color: '#8b949e', fontSize: '10px' }}>
                        Step: {crosslineList.indexOf(selectedCrossline) + 1} / {crosslineList.length}
                      </span>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = crosslineList.indexOf(selectedCrossline)
                          if (curIdx < crosslineList.length - 1) {
                            const step = Math.min(crosslineList.length - 1, curIdx + 10)
                            handleCrosslineChange(crosslineList[step])
                          }
                        }}
                        style={{ opacity: crosslineList.indexOf(selectedCrossline) < crosslineList.length - 1 ? 1 : 0.3, cursor: crosslineList.indexOf(selectedCrossline) < crosslineList.length - 1 ? 'pointer' : 'default', fontSize: '11px' }}
                      >▶▶</span>
                    </div>
                    </>
                  )}
                  {sortMode === 'cdp_offset' && cdpList.length > 0 && (
                    <>
                    <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setCdpTabOffset(Math.max(0, cdpTabOffset - TABS_VISIBLE))}
                        style={{ opacity: cdpTabOffset > 0 ? 1 : 0.3, cursor: cdpTabOffset > 0 ? 'pointer' : 'default' }}
                      >&#9664;</span>
                      <div className="mode-selector inline-tabs" style={{ flex: 1 }}>
                        {cdpList.slice(cdpTabOffset, cdpTabOffset + TABS_VISIBLE).map((cdp) => (
                          <span
                            key={cdp}
                            className={`mode-option${selectedCdp === cdp ? ' active' : ''}`}
                            onClick={() => handleCdpChange(cdp)}
                            style={{ fontSize: '10px', padding: '2px 4px' }}
                          >
                            {cdp}
                          </span>
                        ))}
                      </div>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setCdpTabOffset(Math.min(cdpList.length - TABS_VISIBLE, cdpTabOffset + TABS_VISIBLE))}
                        style={{ opacity: cdpTabOffset + TABS_VISIBLE < cdpList.length ? 1 : 0.3, cursor: cdpTabOffset + TABS_VISIBLE < cdpList.length ? 'pointer' : 'default' }}
                      >&#9654;</span>
                    </div>
                    <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = cdpList.indexOf(selectedCdp)
                          if (curIdx > 0) {
                            const step = Math.max(0, curIdx - 10)
                            handleCdpChange(cdpList[step])
                          }
                        }}
                        style={{ opacity: cdpList.indexOf(selectedCdp) > 0 ? 1 : 0.3, cursor: cdpList.indexOf(selectedCdp) > 0 ? 'pointer' : 'default', fontSize: '11px' }}
                      >◀◀</span>
                      <span style={{ color: '#8b949e', fontSize: '10px' }}>
                        Step: {cdpList.indexOf(selectedCdp) + 1} / {cdpList.length}
                      </span>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = cdpList.indexOf(selectedCdp)
                          if (curIdx < cdpList.length - 1) {
                            const step = Math.min(cdpList.length - 1, curIdx + 10)
                            handleCdpChange(cdpList[step])
                          }
                        }}
                        style={{ opacity: cdpList.indexOf(selectedCdp) < cdpList.length - 1 ? 1 : 0.3, cursor: cdpList.indexOf(selectedCdp) < cdpList.length - 1 ? 'pointer' : 'default', fontSize: '11px' }}
                      >▶▶</span>
                    </div>
                    </>
                  )}
                  {sortMode === 'ffid_offset' && ffidList.length > 0 && (
                    <>
                    <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setFfidTabOffset(Math.max(0, ffidTabOffset - TABS_VISIBLE))}
                        style={{ opacity: ffidTabOffset > 0 ? 1 : 0.3, cursor: ffidTabOffset > 0 ? 'pointer' : 'default' }}
                      >&#9664;</span>
                      <div className="mode-selector inline-tabs" style={{ flex: 1 }}>
                        {ffidList.slice(ffidTabOffset, ffidTabOffset + TABS_VISIBLE).map((ffid) => (
                          <span
                            key={ffid}
                            className={`mode-option${selectedFfid === ffid ? ' active' : ''}`}
                            onClick={() => handleFfidChange(ffid)}
                            style={{ fontSize: '10px', padding: '2px 4px' }}
                          >
                            {ffid}
                          </span>
                        ))}
                      </div>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setFfidTabOffset(Math.min(ffidList.length - TABS_VISIBLE, ffidTabOffset + TABS_VISIBLE))}
                        style={{ opacity: ffidTabOffset + TABS_VISIBLE < ffidList.length ? 1 : 0.3, cursor: ffidTabOffset + TABS_VISIBLE < ffidList.length ? 'pointer' : 'default' }}
                      >&#9654;</span>
                    </div>
                    <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = ffidList.indexOf(selectedFfid)
                          if (curIdx > 0) {
                            const step = Math.max(0, curIdx - 10)
                            handleFfidChange(ffidList[step])
                          }
                        }}
                        style={{ opacity: ffidList.indexOf(selectedFfid) > 0 ? 1 : 0.3, cursor: ffidList.indexOf(selectedFfid) > 0 ? 'pointer' : 'default', fontSize: '11px' }}
                      >&#9664;&#9664;</span>
                      <span style={{ color: '#8b949e', fontSize: '10px' }}>
                        Step: {ffidList.indexOf(selectedFfid) + 1} / {ffidList.length}
                      </span>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = ffidList.indexOf(selectedFfid)
                          if (curIdx < ffidList.length - 1) {
                            const step = Math.min(ffidList.length - 1, curIdx + 10)
                            handleFfidChange(ffidList[step])
                          }
                        }}
                        style={{ opacity: ffidList.indexOf(selectedFfid) < ffidList.length - 1 ? 1 : 0.3, cursor: ffidList.indexOf(selectedFfid) < ffidList.length - 1 ? 'pointer' : 'default', fontSize: '11px' }}
                      >&#9654;&#9654;</span>
                    </div>
                    </>
                  )}
                  {sortMode === 'ffid_chan' && ffidChanList.length > 0 && (
                    <>
                    <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setFfidChanTabOffset(Math.max(0, ffidChanTabOffset - TABS_VISIBLE))}
                        style={{ opacity: ffidChanTabOffset > 0 ? 1 : 0.3, cursor: ffidChanTabOffset > 0 ? 'pointer' : 'default' }}
                      >&#9664;</span>
                      <div className="mode-selector inline-tabs" style={{ flex: 1 }}>
                        {ffidChanList.slice(ffidChanTabOffset, ffidChanTabOffset + TABS_VISIBLE).map((ffid) => (
                          <span
                            key={ffid}
                            className={`mode-option${selectedFfidChan === ffid ? ' active' : ''}`}
                            onClick={() => handleFfidChanChange(ffid)}
                            style={{ fontSize: '10px', padding: '2px 4px' }}
                          >
                            {ffid}
                          </span>
                        ))}
                      </div>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => setFfidChanTabOffset(Math.min(ffidChanList.length - TABS_VISIBLE, ffidChanTabOffset + TABS_VISIBLE))}
                        style={{ opacity: ffidChanTabOffset + TABS_VISIBLE < ffidChanList.length ? 1 : 0.3, cursor: ffidChanTabOffset + TABS_VISIBLE < ffidChanList.length ? 'pointer' : 'default' }}
                      >&#9654;</span>
                    </div>
                    <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = ffidChanList.indexOf(selectedFfidChan)
                          if (curIdx > 0) {
                            const step = Math.max(0, curIdx - 10)
                            handleFfidChanChange(ffidChanList[step])
                          }
                        }}
                        style={{ opacity: ffidChanList.indexOf(selectedFfidChan) > 0 ? 1 : 0.3, cursor: ffidChanList.indexOf(selectedFfidChan) > 0 ? 'pointer' : 'default', fontSize: '11px' }}
                      >&#9664;&#9664;</span>
                      <span style={{ color: '#8b949e', fontSize: '10px' }}>
                        Step: {ffidChanList.indexOf(selectedFfidChan) + 1} / {ffidChanList.length}
                      </span>
                      <span
                        className="inline-tab-arrow"
                        onClick={() => {
                          const curIdx = ffidChanList.indexOf(selectedFfidChan)
                          if (curIdx < ffidChanList.length - 1) {
                            const step = Math.min(ffidChanList.length - 1, curIdx + 10)
                            handleFfidChanChange(ffidChanList[step])
                          }
                        }}
                        style={{ opacity: ffidChanList.indexOf(selectedFfidChan) < ffidChanList.length - 1 ? 1 : 0.3, cursor: ffidChanList.indexOf(selectedFfidChan) < ffidChanList.length - 1 ? 'pointer' : 'default', fontSize: '11px' }}
                      >&#9654;&#9654;</span>
                    </div>
                    </>
                  )}
                </div>
                )}
              </div>
              <div className="subblock">
                <div className="subblock-header" onClick={() => setPaletteOpen(!paletteOpen)}>
                  <span className={`collapse-icon ${paletteOpen ? '' : 'collapsed'}`}>&#9660;</span>
                  <span className="subblock-title">Palette</span>
                </div>
                {paletteOpen && (
                <div className="subblock-body">
                  <div className="param-row">
                    <span className="param-label">Palette</span>
                    <select className="param-select" value={colorscale} onChange={(e) => setColorscale(e.target.value)}>
                      <option value="RdBu">RdBu</option>
                      <option value="Greys">Greyscale</option>
                      <option value="RdYlBu">Red-Yellow-Blue</option>
                      <option value="Picnic">Picnic</option>
                      <option value="Portl">Portl</option>
                      <option value="Electric">Electric</option>
                      <option value="Hot">Hot</option>
                      <option value="Viridis">Viridis</option>
                    </select>
                  </div>
                  <div className="param-row">
                    <span className="param-label">Min</span>
                    <input className="param-input" type="number" style={{ width: '80px' }}
                      value={paletteMin} placeholder="auto"
                      onChange={(e) => setPaletteMin(e.target.value)} />
                    <span className="param-label">Max</span>
                    <input className="param-input" type="number" style={{ width: '80px' }}
                      value={paletteMax} placeholder="auto"
                      onChange={(e) => setPaletteMax(e.target.value)} />
                  </div>
                  <div className="param-row" style={{ justifyContent: 'flex-end' }}>
                    <button className="btn-secondary" style={{ fontSize: '10px', padding: '2px 8px' }}
                      onClick={() => { setPaletteMin(''); setPaletteMax('') }}>Reset Min/Max</button>
                  </div>
                  <div className="param-row">
                    <span className="param-label">Scale</span>
                    <input className="param-input" type="range" min="1" max="500"
                      value={amplitudeScale}
                      onChange={(e) => setAmplitudeScale(Number(e.target.value))}
                      style={{ flex: 1 }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)', minWidth: '32px', textAlign: 'right' }}>{amplitudeScale}%</span>
                  </div>
                  <label className="toggle-row">
                    <span>Colorbar</span>
                    <label className="toggle-switch">
                      <input type="checkbox" checked={showColorbar} onChange={(e) => setShowColorbar(e.target.checked)} />
                      <span className="toggle-slider"></span>
                    </label>
                  </label>
                </div>
                )}
              </div>
            </div>
            )}
          </div>
        </aside>

        <section className="visualization-area">
          {showDisplay && windows.map((win, idx) => win.data && (
            <div key={idx} className="viz-panel">
              <div className="viz-panel-header">
                <span>Win {idx + 1}: {win.fileName || `File ${idx + 1}`}</span>
                {sortMode === 'inline_xline' && win.data?.inline_label != null && (
                  <span className="inline-badge" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>Inline {win.data.inline_label}</span>
                )}
                {sortMode === 'crossline_xline' && win.data?.crossline_label != null && (
                  <span className="inline-badge" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>Xline {win.data.crossline_label}</span>
                )}
                {sortMode === 'cdp_offset' && win.data?.cdp_label != null && (
                  <span className="inline-badge" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>CDP {win.data.cdp_label}</span>
                )}
                {sortMode === 'ffid_offset' && win.data?.ffid_label != null && (
                  <span className="inline-badge" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>FFID {win.data.ffid_label}</span>
                )}
                {sortMode === 'ffid_chan' && win.data?.ffid_label != null && (
                  <span className="inline-badge" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>FFID {win.data.ffid_label}</span>
                )}
                {sortMode === 'time_slice' && win.data?.selected_sample != null && (
                  <span className="inline-badge" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>Sample {win.data.selected_sample}</span>
                )}
                <div className="analysis-dropdown-wrapper" style={{ marginLeft: 'auto' }}>
                  <button
                    className={`btn-spectrum ${selectionPanel === `win${idx}` ? 'active' : ''}`}
                    onClick={() => {
                      if (selectionPanel === `win${idx}`) {
                        setSelectionPanel(null)
                      } else {
                        setDropdownPanel(dropdownPanel === `win${idx}` ? null : `win${idx}`)
                      }
                    }}
                  >
                    {selectionPanel === `win${idx}` ? `Analysis: ${analysisType}` : 'Analysis'}
                  </button>
                  {dropdownPanel === `win${idx}` && !selectionPanel && (
                    <div className="analysis-dropdown">
                      <div className="analysis-dropdown-item" onClick={() => { setAnalysisType('spectrum'); setSelectionPanel(`win${idx}`); setDropdownPanel(null) }}>Spectrum</div>
                      <div className="analysis-dropdown-item" onClick={() => { setAnalysisType('autocorrelation'); setSelectionPanel(`win${idx}`); setDropdownPanel(null) }}>Autocorrelation</div>
                      <div className="analysis-dropdown-item" onClick={() => { setAnalysisType('fxspectrum'); setSelectionPanel(`win${idx}`); setDropdownPanel(null) }}>FX Spectrum</div>
                      <div className="analysis-dropdown-item" onClick={() => { setAnalysisType('signalnoise'); setSelectionPanel(`win${idx}`); setDropdownPanel(null) }}>Signal/Noise</div>
      <div className="analysis-dropdown-item" onClick={() => { setAnalysisType('fkspectrum'); setSelectionPanel(`win${idx}`); setDropdownPanel(null) }}>FK Spectrum</div>
                    </div>
                  )}
                </div>
              </div>
              <Visualization
                data={win.data}
                isLoading={false}
                compact
                selectionMode={selectionPanel === `win${idx}`}
                onSelection={(r) => handleSelection(r, idx)}
                syncView={syncView}
                onViewChange={handleViewChange}
                colorscale={colorscale}
                paletteMin={paletteMin !== '' ? Number(paletteMin) : undefined}
                paletteMax={paletteMax !== '' ? Number(paletteMax) : undefined}
                amplitudeScale={amplitudeScale}
                showColorbar={showColorbar}
                sortMode={sortMode}
              />
            </div>
          ))}
          {showDisplay && showDifference && diffData && numWindows > 1 && (
            <div className="viz-panel">
              <div className="viz-panel-header">
                <span>Difference (Win {diffWinA} − Win {diffWinB})</span>
              </div>
              <Visualization
                data={diffData}
                isLoading={false}
                compact
                syncView={syncView}
                onViewChange={handleViewChange}
                colorscale={colorscale}
                paletteMin={paletteMin !== '' ? Number(paletteMin) : undefined}
                paletteMax={paletteMax !== '' ? Number(paletteMax) : undefined}
                amplitudeScale={amplitudeScale}
                showColorbar={showColorbar}
                sortMode={sortMode}
              />
            </div>
          )}
          {showDatabase && (
            <div className="viz-panel">
              <div className="viz-panel-header">
                <span>Database</span>
              </div>
              <div className="db-panel-body">
                {storedFiles.length === 0 ? (
                  <div className="db-empty">No files in database</div>
                ) : (
                  storedFiles.map((f) => (
                    <div key={f.id} className="db-file-entry" style={{ cursor: 'pointer' }} onClick={() => handleLoadFromDb(f.id)}>
                      <div className="db-file-header">
                        <span className="db-file-name">{f.name.replace(/\.sgy$/i, '')}</span>
                        <div className="db-file-actions">
                          <button className="btn btn-danger" style={{ fontSize: '10px', padding: '2px 6px' }} onClick={(e) => { e.stopPropagation(); handleRemoveFromDb(f.id) }}>Remove</button>
                          {f.is_processed ? <span className="db-badge">processed</span> : null}
                        </div>
                      </div>
                      <div className="db-file-stats-grid">
                        <div className="db-stat-item">
                          <span className="db-stat-label">Traces</span>
                          <span className="db-stat-val">{f.trace_count}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">Samples</span>
                          <span className="db-stat-val">{f.samples_per_trace}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">Rate</span>
                          <span className="db-stat-val">{f.sample_rate?.toFixed(1)} ms</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">Size</span>
                          <span className="db-stat-val db-mono">{f.file_size ? (f.file_size < 1024*1024 ? `${(f.file_size/1024).toFixed(1)} KB` : `${(f.file_size/(1024*1024)).toFixed(1)} MB`) : '—'}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">Min Amp</span>
                          <span className="db-stat-val db-mono">{f.min_amplitude?.toExponential(2) || '—'}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">Max Amp</span>
                          <span className="db-stat-val db-mono">{f.max_amplitude?.toExponential(2) || '—'}</span>
                        </div>
                      </div>
                      <div className="db-file-stats-grid" style={{ marginTop: '4px' }}>
                        <div className="db-stat-item">
                          <span className="db-stat-label">FFID</span>
                          <span className="db-stat-val db-mono">{f.ffid_min}–{f.ffid_max}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">SHOT</span>
                          <span className="db-stat-val db-mono">{f.shot_min}–{f.shot_max}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">CDP</span>
                          <span className="db-stat-val db-mono">{f.cdp_min}–{f.cdp_max}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">OFFSET</span>
                          <span className="db-stat-val db-mono">{f.offset_min}–{f.offset_max}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">INLINE</span>
                          <span className="db-stat-val db-mono">{f.inline_min}–{f.inline_max}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">XLINE</span>
                          <span className="db-stat-val db-mono">{f.xline_min}–{f.xline_max}</span>
                        </div>
                        <div className="db-stat-item">
                          <span className="db-stat-label">CHAN</span>
                          <span className="db-stat-val db-mono">{f.chan_min}–{f.chan_max}</span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </section>
      </main>

      {successMessage && (
        <div className="toast-popup">{successMessage}</div>
      )}

      {spectrumData && (
        <SpectrumModal spectra={spectrumData} onClose={() => setSpectrumData(null)} />
      )}
      {autocorrelationData && (
        <AutocorrelationModal data={autocorrelationData} onClose={() => setAutocorrelationData(null)} />
      )}
      {fxSpectrumData && (
        <FxSpectrumModal data={fxSpectrumData} onClose={() => setFxSpectrumData(null)} />
      )}
{signalNoiseData && (
  <SnrModal data={signalNoiseData} onClose={() => setSignalNoiseData(null)} />
)}
{fkSpectrumData && (
  <FkSpectrumModal data={fkSpectrumData} onClose={() => setFkSpectrumData(null)} />
)}

      {isProcessing && processingSteps.length > 0 && (
        <ProcessingModal steps={processingSteps} onCancel={handleCancelProcessing} />
      )}
    </div>
  )
}

export default App