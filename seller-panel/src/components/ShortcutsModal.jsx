import s from './ShortcutsModal.module.css'

const SHORTCUT_GROUPS = [
  {
    title: 'Навигация',
    items: [
      { keys: ['g', 'p'], desc: 'Товары' },
      { keys: ['g', 'o'], desc: 'Заказы' },
      { keys: ['g', 'c'], desc: 'Покупатели' },
      { keys: ['g', 's'], desc: 'Статистика' },
      { keys: ['g', 'i'], desc: 'Импорт' },
      { keys: ['g', 'S'], desc: 'Настройки' },
      { keys: ['g', 'b'], desc: 'Биллинг' },
      { keys: ['g', 'r'], desc: 'Отзывы' },
    ],
  },
  {
    title: 'Интерфейс',
    items: [
      { keys: ['?'],       desc: 'Показать / скрыть это окно' },
      { keys: ['Esc'],     desc: 'Закрыть модальное окно' },
    ],
  },
]

export default function ShortcutsModal({ onClose }) {
  return (
    <div className={s.overlay} role="dialog" aria-modal="true" aria-label="Горячие клавиши">
      <div className={s.modal}>
        <div className={s.header}>
          <span className={s.title}>⌨️ Горячие клавиши</span>
          <button className={s.close} onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        <div className={s.body}>
          {SHORTCUT_GROUPS.map(group => (
            <div key={group.title} className={s.group}>
              <div className={s.groupTitle}>{group.title}</div>
              {group.items.map((item, i) => (
                <div key={i} className={s.row}>
                  <div className={s.keys}>
                    {item.keys.map((k, ki) => (
                      <span key={ki}>
                        <kbd className={s.kbd}>{k}</kbd>
                        {ki < item.keys.length - 1 && <span className={s.then}>then</span>}
                      </span>
                    ))}
                  </div>
                  <span className={s.desc}>{item.desc}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
