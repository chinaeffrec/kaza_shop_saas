import s from './ToggleSwitch.module.css'

export default function ToggleSwitch({ checked, onChange, label }) {
  return (
    <label className={s.wrapper}>
      <span className={s.track} data-on={checked}>
        <span className={s.thumb} />
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className={s.input}
      />
      {label && <span className={s.label}>{label}</span>}
    </label>
  )
}