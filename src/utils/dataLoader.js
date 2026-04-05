// Data loader — fetches JSON files from /data/ directory (static hosting compatible)

function extractDate(filename) {
  const match = filename.match(/(\d{4}-\d{2}-\d{2})/)
  return match ? match[1] : null
}

function sortByDateDesc(files) {
  return [...files].sort((a, b) => {
    const da = extractDate(a) || ''
    const db = extractDate(b) || ''
    return db.localeCompare(da)
  })
}

let manifestCache = null

async function getManifest() {
  if (manifestCache) return manifestCache
  try {
    const res = await fetch('/data/manifest.json')
    manifestCache = await res.json()
    return manifestCache
  } catch {
    return {}
  }
}

async function listFiles(folder) {
  const manifest = await getManifest()
  return manifest[folder] || []
}

async function loadFile(filePath) {
  try {
    const res = await fetch(`/data/${filePath}`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

async function loadLatestFromFolder(folder, prefix) {
  const files = await listFiles(folder)
  const matching = prefix ? files.filter(f => f.startsWith(prefix)) : files
  const sorted = sortByDateDesc(matching)

  const current = sorted[0] ? await loadFile(`${folder}/${sorted[0]}`) : null
  const prior = sorted[1] ? await loadFile(`${folder}/${sorted[1]}`) : null
  const all = []

  // Load up to 12 weeks of history
  for (let i = 0; i < Math.min(sorted.length, 12); i++) {
    const data = await loadFile(`${folder}/${sorted[i]}`)
    if (data) {
      all.push({ date: extractDate(sorted[i]), data })
    }
  }

  return {
    current,
    prior,
    history: all.reverse(), // oldest first for charts
    currentDate: sorted[0] ? extractDate(sorted[0]) : null,
    priorDate: sorted[1] ? extractDate(sorted[1]) : null,
  }
}

export async function loadAllData() {
  const [scData, ciData, plData, vocData, copyData, ppcData, kwData] = await Promise.all([
    loadLatestFromFolder('sc_data', 'SC_Data'),
    loadLatestFromFolder('ci_data', 'CI_Data'),
    loadLatestFromFolder('pl_data', 'PL_Data'),
    loadLatestFromFolder('voc_data', 'VoC_Data'),
    loadLatestFromFolder('copy', 'Copy_Variants'),
    loadLatestFromFolder('sc_data', 'PPC_Analysis'),
    loadLatestFromFolder('kw_data', 'KW_Data'),
  ])

  const [plConfig, experimentLog] = await Promise.all([
    loadFile('pl_data/pl_config.json'),
    loadFile('experiment_log.json'),
  ])

  return {
    sc: scData,
    ci: ciData,
    pl: plData,
    voc: vocData,
    copy: copyData,
    ppc: ppcData,
    kw: kwData,
    plConfig,
    experimentLog,
  }
}
