export function ClientAddressFields({ postalCode, address, onPostalChange, onAddressChange, message, choices, onChoose }: {
  postalCode: string;
  address: string;
  onPostalChange: (value: string) => void;
  onAddressChange: (value: string) => void;
  message: string;
  choices: string[];
  onChoose: (address: string) => void;
}) {
  return <fieldset className="master-address-group">
    <legend>住所情報</legend>
    <label style={{ maxWidth: 220 }}>郵便番号<input aria-label="郵便番号" inputMode="numeric" autoComplete="postal-code" placeholder="例: 123-4567" value={postalCode} onChange={(event) => onPostalChange(event.target.value)} /></label>
    <p className="master-address-help">郵便番号7桁から住所を補完します。番地・建物名は確認して入力してください。</p>
    {message && <p role="status">{message}</p>}
    {choices.map((choice) => <button key={choice} type="button" className="ghost-button" onClick={() => onChoose(choice)}>{choice}</button>)}
    <label>住所<textarea aria-label="住所" rows={3} value={address} onChange={(event) => onAddressChange(event.target.value)} /></label>
  </fieldset>;
}
