import { useState, useRef } from 'react'
import { api } from '../api.js'
import s from './ImportPage.module.css'

export default function ImportPage() {
  const [dragging, setDragging] = useState(false)
  const [file, setFile]         = useState(null)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)
  const inputRef                = useRef()

  function pickFile(f) {
    if (!f.name.endsWith('.xlsx') && !f.name.endsWith('.xls')) { setError('Только .xlsx или .xls файлы'); return }
    setFile(f); setResult(null); setError(null)
  }

  async function handleUpload() {
    if (!file) return
    setLoading(true); setResult(null); setError(null)
    try {
      const res = await api.importXlsx(file)
      setResult(res); setFile(null)
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div>
      <h1 className={s.title}>Импорт каталога</h1>
      <p className={s.hint}>
        Загрузите .xlsx файл с колонками:{' '}
        {['category','subcategory','name','price','discount_price','description','characteristics', 'stock', 'is_active']
          .map(c => <code key={c}>{c}</code>).reduce((a,b)=>[a,', ',b])}
      </p>

      <div
        className={`${s.dropzone} ${dragging?s.dragging:''} ${file?s.hasFile:''}`}
        onDragOver={e=>{e.preventDefault();setDragging(true)}}
        onDragLeave={()=>setDragging(false)}
        onDrop={e=>{e.preventDefault();setDragging(false);const f=e.dataTransfer.files[0];if(f)pickFile(f)}}
        onClick={()=>inputRef.current.click()}
      >
        <input ref={inputRef} type="file" accept=".xlsx,.xls" style={{display:'none'}}
          onChange={e=>e.target.files[0]&&pickFile(e.target.files[0])} />
        {file ? (
          <div className={s.fileInfo}>
            <span className={s.fileIcon}>📄</span>
            <span className={s.fileName}>{file.name}</span>
            <span className={s.fileSize}>{(file.size/1024).toFixed(1)} KB</span>
          </div>
        ) : (
          <div className={s.dropText}>
            <span className={s.dropIcon}>📥</span>
            <span>Перетащите .xlsx файл сюда</span>
            <span className={s.or}>или нажмите для выбора</span>
          </div>
        )}
      </div>

      {file && (
        <button className={s.btnUpload} onClick={handleUpload} disabled={loading}>
          {loading ? 'Загрузка...' : '⬆️ Загрузить'}
        </button>
      )}

      {result && (
        <div className={s.success}>
          ✅ Импорт завершён: создано <b>{result.created}</b>, обновлено <b>{result.updated}</b>
          {result.errors?.length > 0 && (
            <div className={s.errList}>
              <b>Ошибки:</b>
              {result.errors.map((e,i) => <div key={i} className={s.errLine}>{e}</div>)}
            </div>
          )}
        </div>
      )}
      {error && <div className={s.errorBox}>❌ {error}</div>}

      <div className={s.template}>
        <h2 className={s.sectionTitle}>Шаблон файла</h2>
        <table className={s.tpl}>
          <thead>
            <tr>
              <th>category</th><th>subcategory</th><th>name</th><th>price</th>
              <th>discount_price</th><th>description</th><th>characteristics</th><th>stock</th><th>is_active</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Электроника</td><td>Смартфоны</td><td>iPhone 16</td><td>89990</td>
              <td>79990</td><td>Флагман Apple</td><td>RAM: 8GB</td><td>15</td><td>True</td>
            </tr>
            <tr>
              <td>Напитки</td><td>Соки</td><td>Апельсиновый сок</td><td>120</td>
              <td></td><td>Свежевыжатый</td><td></td><td>50</td><td>True</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
