import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api.js'
import s from './ProductsPage.module.css'
import ToggleSwitch from "../components/ToggleSwitch.jsx";
import { useToast } from '../components/Toast.jsx'

const EMPTY = {
  name: '',
  price: '',
  discount_price: '',
  subcategory_id: '',
  description: '',
  characteristics: '',
  stock: 0,
  is_active: true,
  _cat_id: ''
}
const PER_PAGE = 20

export default function ProductsPage() {
  const toast = useToast()
  const [products, setProducts]           = useState([])
  const [productsPage, setProductsPage]   = useState(1)
  const [productsTotal, setProductsTotal] = useState(0)
  const [productsPages, setProductsPages] = useState(1)
  const [categories, setCategories]       = useState([])
  const [allSubcats, setAllSubcats]       = useState({})
  const [subcats, setSubcats]             = useState([])
  const [loading, setLoading]             = useState(true)
  const [search, setSearch]               = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [filterCat, setFilterCat]         = useState('')
  const [filterSub, setFilterSub]         = useState('')
  const [filterSubOpts, setFilterSubOpts] = useState([])
  const [onlyNoPhoto, setOnlyNoPhoto]     = useState(false)
  const [modal, setModal]                 = useState(null)
  const [form, setForm]                   = useState(EMPTY)
  const [photoFile, setPhotoFile]         = useState(null)
  const [photoPreview, setPhotoPreview]   = useState(null)
  const [extraPhotos, setExtraPhotos]     = useState({})
  const [extraPreviews, setExtraPreviews] = useState({})
  const [saving, setSaving]               = useState(false)
  const [hideNoStock, setHideNoStock]     = useState(false)
  const [selectedIds, setSelectedIds]     = useState([])
  const searchTimer = useRef(null)

  // Дебаунс поиска — запрос идёт через 400 мс после последнего нажатия
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 400)
    return () => clearTimeout(searchTimer.current)
  }, [search])

  // Загрузка справочников — 3 параллельных запроса вместо N+1
  useEffect(() => {
    async function loadMeta() {
      try {
        const [cats, allSubs, cfg] = await Promise.all([
          api.getCategories(),
          api.getAllSubcategories(),
          api.getSettings(),
        ])
        setHideNoStock(cfg.hide_out_of_stock || false)
        setCategories(cats)

        const catMap = Object.fromEntries(cats.map(c => [c.id, c.name]))
        const subMap = {}
        for (const sub of allSubs)
          subMap[sub.id] = { name: sub.name, category_name: catMap[sub.category_id] || '—', category_id: sub.category_id }
        setAllSubcats(subMap)
      } catch (e) {
        toast('Ошибка загрузки справочников: ' + e.message)
      }
    }
    loadMeta()
  }, [])

  // Загрузка товаров — при изменении страницы или фильтров
  const loadProducts = useCallback(async (page = 1) => {
    setLoading(true)
    try {
      const filters = {}
      if (debouncedSearch) filters.search = debouncedSearch
      if (filterSub)       filters.subcategory_id = filterSub
      else if (filterCat)  filters.category_id = filterCat
      if (onlyNoPhoto)     filters.has_image = false

      const res = await api.getProducts(page, PER_PAGE, filters)
      setProducts(res.items || [])
      setProductsTotal(res.total || 0)
      setProductsPages(res.pages || 1)
      setProductsPage(page)
    } catch (e) {
      toast('Ошибка загрузки товаров: ' + e.message)
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, filterCat, filterSub, onlyNoPhoto])

  // При смене фильтров — сбрасываем на страницу 1
  useEffect(() => {
    loadProducts(1)
    setSelectedIds([])
  }, [loadProducts])

  useEffect(() => {
    if (!filterCat) { setFilterSubOpts([]); setFilterSub(''); return }
    api.getSubcategories(filterCat).then(setFilterSubOpts).catch(() => {})
    setFilterSub('')
  }, [filterCat])

  useEffect(() => {
    if (!form._cat_id) { setSubcats([]); return }
    api.getSubcategories(form._cat_id).then(setSubcats).catch(() => setSubcats([]))
  }, [form._cat_id])

  useEffect(() => {
    setSelectedIds([])
  }, [productsPage])

  function openAdd() {
    setForm(EMPTY)
    setPhotoFile(null)
    setPhotoPreview(null)
    setExtraPhotos({})
    setExtraPreviews({})
    setModal({ type: 'add' })
  }

  function openEdit(p) {
    const sub = allSubcats?.[p.subcategory_id]
    setForm({
      name: p.name,
      price: String(p.price),
      discount_price: String(p.discount_price || ''),
      subcategory_id: String(p.subcategory_id),
      description: p.description || '',
      characteristics: p.characteristics || '',
      stock: p.stock || 0,
      is_active: p.is_active,
      _cat_id: sub?.category_id ? String(sub.category_id) : ''
    })
    setPhotoFile(null)
    setPhotoPreview(p.image_url ? api.BASE + p.image_url : null)
    setExtraPhotos({})
    setExtraPreviews({
      2: p.image_url_2 ? api.BASE + p.image_url_2 : null,
      3: p.image_url_3 ? api.BASE + p.image_url_3 : null,
    })
    setModal({ type: 'edit', product: p })
  }

  async function handleSave() {
    if (!form.name.trim()) return toast('Введите название')
    if (!form.price) return toast('Введите цену')
    if (!form.subcategory_id) return toast('Выберите категорию и подкатегорию')

    const isEdit = modal?.type === 'edit'
    const productId = modal?.product?.id  // захватываем до закрытия модала
    const capturedPhoto = photoFile
    const capturedExtras = { ...extraPhotos }

    const payload = {
      name: form.name.trim(),
      price: parseInt(form.price),
      discount_price: form.discount_price ? parseInt(form.discount_price) : null,
      subcategory_id: parseInt(form.subcategory_id),
      description: form.description || null,
      characteristics: form.characteristics || null,
      stock: parseInt(form.stock) || 0,
      is_active: form.is_active,
    }

    // Для редактирования — закрываем карточку сразу, не ждём сервер
    if (isEdit) {
      setModal(null)
      setPhotoFile(null)
      setPhotoPreview(null)
      setExtraPhotos({})
      setExtraPreviews({})
    } else {
      setSaving(true)
    }

    try {
      const saved = isEdit
        ? await api.updateProduct(productId, payload)
        : await api.createProduct(payload)

      // Для добавления закрываем после получения ID (нужен для фото)
      if (!isEdit) {
        setModal(null)
        setPhotoFile(null)
        setPhotoPreview(null)
        setExtraPhotos({})
        setExtraPreviews({})
      }

      loadProducts(productsPage)

      // Фото загружаются в фоне
      if (capturedPhoto) {
        api.uploadPhotoSlot(saved.id, 1, capturedPhoto)
          .then(() => loadProducts(productsPage))
          .catch(e => toast('Ошибка загрузки фото: ' + e.message))
      }
      for (const [slot, file] of Object.entries(capturedExtras)) {
        if (file) {
          api.uploadPhotoSlot(saved.id, parseInt(slot), file)
            .then(() => loadProducts(productsPage))
            .catch(e => toast(`Ошибка загрузки фото ${slot}: ` + e.message))
        }
      }
    } catch (e) {
      console.error(e)
      toast('Ошибка сохранения: ' + (e.message || e))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!confirm('Удалить товар?')) return
    await api.deleteProduct(id).catch(e => toast(e.message))
    await loadProducts(productsPage)
  }

  async function handleBulkDelete() {
    if (selectedIds.length === 0) return
    if (!confirm(`Удалить выбранные товары (${selectedIds.length})?`)) return
    try {
      const res = await api.bulkDeleteProducts(selectedIds)
      toast(`Удалено товаров: ${res.deleted ?? selectedIds.length}`)
      setSelectedIds([])
      await loadProducts(1)
    } catch (e) {
      toast(e.message || 'Ошибка массового удаления')
    }
  }

  async function handleDeletePhotoSlot(productId, slot) {
    await api.deletePhotoSlot(productId, slot).catch(e => toast(e.message))
    await loadProducts(productsPage)
  }

  async function toggleActive(p) {
    await api.toggleActive(p.id, !p.is_active).catch(e => toast(e.message))
    await loadProducts(productsPage)
  }

  async function toggleHideNoStock(val) {
    setHideNoStock(val)
    await api.updateSettings({ hide_out_of_stock: val }).catch(() => {})
    await api.reloadCache()
  }

  // Фильтрация и пагинация полностью на сервере — products уже нужная страница
  const visible = products
  const visibleIds = visible.map(p => p.id)
  const selectedVisibleCount = selectedIds.filter(id => visibleIds.includes(id)).length
  const allVisibleSelected = visible.length > 0 && selectedVisibleCount === visible.length

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Товары <span className={s.count}>{productsTotal}</span></h1>
        <div style={{display:'flex', gap:8}}>
          {selectedIds.length > 0 && (
            <button className={s.btnDel} onClick={handleBulkDelete}>
              🗑 Удалить выбранные ({selectedIds.length})
            </button>
          )}
          <button className={s.btnAdd} onClick={openAdd}>+ Добавить</button>
        </div>
      </div>

      <div className={s.filters}>
        <input className={s.search} placeholder="Поиск..." value={search}
          onChange={e => setSearch(e.target.value)} />
        <select className={s.filterSelect} value={filterCat}
          onChange={e => setFilterCat(e.target.value)}>
          <option value="">Все категории</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {filterSubOpts.length > 0 && (
          <select className={s.filterSelect} value={filterSub}
            onChange={e => setFilterSub(e.target.value)}>
            <option value="">Все подкатегории</option>
            {filterSubOpts.map(sc => <option key={sc.id} value={sc.id}>{sc.name}</option>)}
          </select>
        )}
        <ToggleSwitch checked={onlyNoPhoto} onChange={setOnlyNoPhoto} label="Без фото" />
        <ToggleSwitch checked={hideNoStock} onChange={toggleHideNoStock} label="Скрыть для покупателя товары без остатка" />
      </div>

      {productsPages > 1 && (
        <div style={{display:'flex', gap:8, alignItems:'center', marginBottom:12, fontSize:13, color:'#555'}}>
          <button onClick={() => loadProducts(Math.max(1, productsPage - 1))} disabled={productsPage <= 1}
            style={{padding:'4px 12px', borderRadius:6, border:'1px solid #ddd', background:'#fff', cursor:productsPage<=1?'default':'pointer'}}>
            ←
          </button>
          <span>Стр. {productsPage} из {productsPages} (всего {productsTotal})</span>
          <button onClick={() => loadProducts(Math.min(productsPages, productsPage + 1))} disabled={productsPage >= productsPages}
            style={{padding:'4px 12px', borderRadius:6, border:'1px solid #ddd', background:'#fff', cursor:productsPage>=productsPages?'default':'pointer'}}>
            →
          </button>
        </div>
      )}

      {loading ? (
        <p className={s.msg}>Загрузка...</p>
      ) : visible.length === 0 ? (
        <p className={s.msg}>Товары не найдены</p>
      ) : (
        <table className={s.table}>
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedIds(prev => Array.from(new Set([...prev, ...visibleIds])))
                    } else {
                      setSelectedIds(prev => prev.filter(id => !visibleIds.includes(id)))
                    }
                  }}
                />
              </th>
              <th>Фото</th><th>Название</th><th>Категория</th><th>Подкатегория</th>
              <th>Цена</th><th>Цена со скидкой</th><th>Остаток</th><th>Активен</th><th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(p => (
              <tr key={p.id} className={!p.has_image ? s.noPhotoRow : ''}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(p.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedIds(prev => prev.includes(p.id) ? prev : [...prev, p.id])
                      } else {
                        setSelectedIds(prev => prev.filter(id => id !== p.id))
                      }
                    }}
                  />
                </td>
                <td>
                  {p.image_url
                    ? <img src={`${api.BASE}${p.image_url}?v=${p.updated_at || ''}`}
                           className={s.thumb} alt=""
                           onError={e => { e.target.style.display = 'none' }} />
                    : <span className={s.noPhotoBadge}>нет</span>}
                </td>
                <td className={s.nameCell}>{p.name}</td>
                <td className={s.subCell}>{allSubcats[p.subcategory_id]?.category_name || '—'}</td>
                <td className={s.subCell}>{allSubcats[p.subcategory_id]?.name || '—'}</td>
                <td>{(p.price || 0).toLocaleString()} ₽</td>
                <td>{p.discount_price
                  ? <span className={s.discount}>{p.discount_price.toLocaleString()} ₽</span>
                  : '—'}</td>
                <td className={s.stockCell}>{p.stock ?? 0}</td>
                <td>
                  <button className={p.is_active ? s.activeBadge : s.inactiveBadge}
                          onClick={() => toggleActive(p)} title="Нажмите чтобы переключить">
                    {p.is_active ? 'Да' : 'Нет'}
                  </button>
                </td>
                <td className={s.actions}>
                  <button className={s.btnEdit} onClick={() => openEdit(p)}>✏️</button>
                  <button className={s.btnDel} onClick={() => handleDelete(p.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modal && (
        <div className={s.overlay} onClick={e => e.target === e.currentTarget && setModal(null)}>
          <div className={s.modalBox}>
            <h2 className={s.modalTitle}>
              {modal?.type === 'add' ? 'Добавить товар' : 'Редактировать товар'}
            </h2>

            <label className={s.label}>Название *
              <input className={s.input} value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </label>

            <div style={{ display: 'flex', gap: 12 }}>
              <label className={s.label} style={{ flex: 1 }}>Цена (₽) *
                <input className={s.input} type="number" value={form.price}
                  onChange={e => setForm(f => ({ ...f, price: e.target.value }))} />
              </label>
              <label className={s.label} style={{ flex: 1 }}>Цена со скидкой
                <input className={s.input} type="number" value={form.discount_price}
                  onChange={e => setForm(f => ({ ...f, discount_price: e.target.value }))} />
              </label>
            </div>

            <label className={s.label}>Категория *
              <select className={s.input} value={form._cat_id}
                onChange={e => setForm(f => ({ ...f, _cat_id: e.target.value, subcategory_id: '' }))}>
                <option value="">— выберите —</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>

            <label className={s.label}>Подкатегория *
              <select className={s.input} value={form.subcategory_id}
                onChange={e => setForm(f => ({ ...f, subcategory_id: e.target.value }))}>
                <option value="">— выберите —</option>
                {subcats.map(sc => <option key={sc.id} value={sc.id}>{sc.name}</option>)}
              </select>
            </label>

            <label className={s.label}>Описание
              <textarea className={s.input} rows={3} value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </label>

            <label className={s.label}>Характеристики
              <textarea className={s.input} rows={2} value={form.characteristics}
                onChange={e => setForm(f => ({ ...f, characteristics: e.target.value }))} />
            </label>

            <label className={s.label}>Остаток (шт)
              <input className={s.input} type="number" min="0" value={form.stock}
                onChange={e => setForm(f => ({ ...f, stock: e.target.value }))} />
            </label>

            {/* Фото 1, 2, 3 */}
            {[1, 2, 3].map(slot => {
              const isMain = slot === 1
              const preview = isMain
                ? photoPreview
                : extraPreviews[slot] || null
              const existingUrl = modal?.product?.[isMain ? 'image_url' : `image_url_${slot}`]

              return (
                <label key={slot} className={s.label}>
                  {isMain ? 'Фото 1 (основное)' : `Фото ${slot} (дополнительное)`}
                  {preview && (
                    <img src={preview} alt={`preview ${slot}`} style={{
                      width: 80, height: 80, objectFit: 'cover',
                      borderRadius: 8, marginBottom: 6, display: 'block'
                    }} />
                  )}
                  <div style={{display:'flex', gap:8, alignItems:'center'}}>
                    <input type="file" accept="image/jpeg,image/png,image/webp"
                      style={{flex:1}}
                      onChange={e => {
                        const f = e.target.files[0]
                        if (!f) return
                        const url = URL.createObjectURL(f)
                        if (isMain) {
                          setPhotoFile(f)
                          setPhotoPreview(url)
                        } else {
                          setExtraPhotos(prev => ({ ...prev, [slot]: f }))
                          setExtraPreviews(prev => ({ ...prev, [slot]: url }))
                        }
                      }} />
                    {existingUrl && modal?.type === 'edit' && (
                      <button type="button" className={s.btnDel}
                        onClick={async () => {
                          if (!confirm('Удалить фото?')) return
                          await api.deletePhotoSlot(modal.product.id, slot)
                          if (isMain) {
                            setPhotoPreview(null)
                            setPhotoFile(null)
                          } else {
                            setExtraPreviews(prev => ({ ...prev, [slot]: null }))
                          }
                          await loadProducts(productsPage)
                        }}
                        title="Удалить фото">🗑</button>
                    )}
                  </div>
                </label>
              )
            })}

            <ToggleSwitch checked={form.is_active}
                          onChange={val => setForm(f => ({ ...f, is_active: val }))}
                          label="Активен (показывать в боте)" />

            <div className={s.modalFooter}>
              <button className={s.btnCancel} onClick={() => setModal(null)}>Отмена</button>
              <button className={s.btnSave} onClick={handleSave} disabled={saving}>
                {saving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
