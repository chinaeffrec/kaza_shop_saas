import { useEffect, useRef } from 'react'

/**
 * Global keyboard shortcuts with "vim-style" two-key sequences (e.g. g+p).
 *
 * shortcuts: array of { keys: string[], action: () => void, description: string }
 *   keys can be single ("?") or two characters ("gp" handled as sequence).
 *
 * Returns nothing; call with the shortcuts list and a navigate callback.
 */
export function useKeyboardShortcuts(shortcuts, { enabled = true } = {}) {
  const pendingKey = useRef(null)
  const pendingTimer = useRef(null)

  useEffect(() => {
    if (!enabled) return

    function onKeyDown(e) {
      // Skip if user is typing in an input/textarea/select/contenteditable
      const tag = e.target.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.target.isContentEditable) return
      // Skip modified keys (Ctrl/Alt/Meta combos)
      if (e.ctrlKey || e.altKey || e.metaKey) return

      const key = e.key

      // Handle pending two-key sequence
      if (pendingKey.current) {
        const seq = pendingKey.current + key
        clearTimeout(pendingTimer.current)
        pendingKey.current = null

        const match = shortcuts.find(s => s.keys === seq)
        if (match) {
          e.preventDefault()
          match.action()
        }
        return
      }

      // Check for exact single-key match first
      const singleMatch = shortcuts.find(s => s.keys === key && s.keys.length === 1)
      if (singleMatch) {
        e.preventDefault()
        singleMatch.action()
        return
      }

      // Check if any shortcut starts with this key (two-key prefix)
      const hasTwoKey = shortcuts.some(s => s.keys.length === 2 && s.keys[0] === key)
      if (hasTwoKey) {
        pendingKey.current = key
        pendingTimer.current = setTimeout(() => {
          pendingKey.current = null
        }, 1000) // 1s to complete the sequence
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      clearTimeout(pendingTimer.current)
    }
  }, [shortcuts, enabled])
}

/**
 * Build shortcuts list for the seller panel.
 * Returns array of { keys, label, description, action }
 */
export function buildShortcuts(setPage, { canViewPage } = {}) {
  const go = (id) => () => canViewPage?.(id) !== false && setPage(id)
  return [
    { keys: 'gp', label: 'g p', description: 'Перейти: Товары',      action: go('products') },
    { keys: 'go', label: 'g o', description: 'Перейти: Заказы',       action: go('orders')   },
    { keys: 'gc', label: 'g c', description: 'Перейти: Покупатели',   action: go('customers')},
    { keys: 'gs', label: 'g s', description: 'Перейти: Статистика',   action: go('stats')    },
    { keys: 'gi', label: 'g i', description: 'Перейти: Импорт',       action: go('import')   },
    { keys: 'gS', label: 'g S', description: 'Перейти: Настройки',    action: go('settings') },
    { keys: 'gb', label: 'g b', description: 'Перейти: Биллинг',      action: go('billing')  },
    { keys: 'gr', label: 'g r', description: 'Перейти: Отзывы',       action: go('reviews')  },
  ]
}
