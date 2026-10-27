import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, getPlaceStatus, searchPlaces, type PlaceSearchItem } from "../lib/api/client";
import { lookupPostalAddress, normalizePostalCode } from "../lib/postalAddress";

function Attribution({ item }: { item: PlaceSearchItem }) {
  return <>{item.attributions.map((attribution, i) => <span key={i}>{attribution.providerUri && /^https:\/\//.test(attribution.providerUri) ? <a href={attribution.providerUri} target="_blank" rel="noopener noreferrer">{attribution.provider ?? "情報提供元"}</a> : attribution.provider ?? ""}</span>)}</>;
}

export function OrderLocationEditor({ disabled, venueName, address, placeId, savedMapsUrl, onMapsUrl, onAddress, onPlaceId }: {
  disabled: boolean; venueName: string; address: string; placeId: string; savedMapsUrl: string; onMapsUrl: (url: string) => void; onAddress: (address: string) => void; onPlaceId: (placeId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PlaceSearchItem[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [postalCode, setPostalCode] = useState(() => address.match(/^〒?\s*(\d{3}-?\d{4})/)?.[1] ?? "");
  const [postalMessage, setPostalMessage] = useState("");
  const [postalChoices, setPostalChoices] = useState<string[]>([]);
  const postalTouched = useRef(false);
  const lastAutoAddress = useRef("");
  const addressState = useRef({ address, onAddress });
  addressState.current = { address, onAddress };
  const addressRevision = useRef(0);
  useEffect(() => {
    if (disabled || !postalTouched.current) return;
    const postal = normalizePostalCode(postalCode);
    if (!/^[0-9]{7}$/.test(postal)) return;
    const controller = new AbortController();
    const revision = addressRevision.current;
    const timer = setTimeout(async () => {
      setPostalMessage("住所を検索中...");
      try {
        const choices = await lookupPostalAddress(postal, controller.signal);
        if (controller.signal.aborted) return;
        const values = choices.map((choice) => `〒${postal.slice(0, 3)}-${postal.slice(3)} ${choice.prefecture}${choice.address}`);
        const current = addressState.current;
        if (values.length === 1 && revision === addressRevision.current && (!current.address.trim() || current.address === lastAutoAddress.current)) {
          current.onAddress(values[0]);
          lastAutoAddress.current = values[0];
          setPostalMessage("番地・建物名を確認して入力してください。");
        } else {
          setPostalChoices(values);
          setPostalMessage(values.length ? "住所の候補を選択してください。入力済みの住所は自動で変更しません。" : "該当する住所がありません。住所を直接入力してください。");
        }
      } catch {
        if (!controller.signal.aborted) setPostalMessage("住所を取得できませんでした。住所を直接入力してください。");
      }
    }, 350);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [postalCode, disabled]);
  const inputVersion = useRef(0);
  const [picked, setPicked] = useState<PlaceSearchItem | null>(null);
  const status = useQuery({ queryKey: ["place-search-status"], queryFn: getPlaceStatus, retry: false });
  useEffect(() => { setQuery(venueName.split("\n")[0]); setItems([]); setSearched(false); setPicked(null); inputVersion.current += 1; }, [venueName]);
  const search = useMutation({ mutationFn: ({ text }: { text: string; version: number }) => searchPlaces(text), onSuccess: (data, request) => {
    if (request.version !== inputVersion.current) return;
    setItems(data.items); setSearched(true); setError("");
  }, onError: (e, request) => { if (request.version === inputVersion.current) setError(e instanceof ApiError ? e.message : "所在地を取得できませんでした"); } });
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query || venueName || address)}${placeId ? `&query_place_id=${encodeURIComponent(placeId)}` : ""}`;
  return <div className="order-location order-span-12">
    <div className="order-postal-heading"><label htmlFor="order-site-postal">郵便番号</label><span className="order-field-hint">郵便番号7桁から住所を補完します。番地・建物名は確認して入力してください。</span></div>
    <input id="order-site-postal" className="order-postal-input" aria-label="稼働場所の郵便番号" inputMode="numeric" autoComplete="postal-code" value={postalCode} disabled={disabled} placeholder="例: 231-0001" onChange={(event) => { postalTouched.current = true; setPostalCode(event.target.value); setPostalMessage(""); setPostalChoices([]); }} />
    {postalMessage && <p className="order-field-hint" role="status">{postalMessage}</p>}
    {postalChoices.map((choice) => <button key={choice} type="button" className="btn btn-ghost order-address-choice" disabled={disabled} onClick={() => { onAddress(choice); lastAutoAddress.current = choice; setPostalChoices([]); setPostalMessage("番地・建物名を確認して入力してください。"); }}>{choice}</button>)}
    <label className="order-field">稼働場所の住所<textarea rows={2} value={address} disabled={disabled} placeholder="〒231-0001 神奈川県横浜市中区新港1丁目1−1" onChange={(e) => { addressRevision.current += 1; onAddress(e.target.value); }} /></label>
    <a href={mapsUrl} target="_blank" rel="noopener noreferrer">Google Mapsで所在地を検索</a>
    <label className="order-field">Google Mapsの共有URL<input type="url" value={savedMapsUrl} maxLength={4096} disabled={disabled} placeholder="https://maps.app.goo.gl/…" onChange={(e) => onMapsUrl(e.target.value)} /></label>
    <p className="order-field-hint">Google Mapsで会場を開き、「共有」→「リンクをコピー」で取得したURLを貼り付けます。この方式ではMaps APIを使用しません。</p>
    {savedMapsUrl && /^https:\/\/(?:maps\.app\.goo\.gl|(?:www\.|maps\.)?google\.(?:com|co\.jp)|goo\.gl)\//.test(savedMapsUrl.trim()) && <a href={savedMapsUrl.trim()} target="_blank" rel="noopener noreferrer">登録した会場をGoogle Mapsで開く</a>}
    {!disabled && status.data?.configured && <details><summary>APIによる会場検索</summary>
      <div className="order-location-search"><label className="order-field">Google Mapsの会場検索<input value={query} maxLength={200} onChange={(e) => { setQuery(e.target.value); setItems([]); setSearched(false); setError(""); inputVersion.current += 1; }} /></label>
        <button type="button" className="btn btn-ghost" disabled={!status.data?.configured || query.trim().length < 2 || search.isPending} onClick={() => search.mutate({ text: query.trim(), version: inputVersion.current })}>{search.isPending ? "検索中..." : "所在地を検索"}</button></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {searched && !items.length && <p>該当する会場がありません。名称や地域を変えて検索してください。</p>}
      {items.length > 0 && <div className="google-place-results"><span className="google-maps-attribution" translate="no">Google Maps</span>{items.map((item) => <div className="google-place-result" key={item.place_id}><strong>{item.name}</strong><p>{item.address}</p>
        <button type="button" className="btn btn-ghost" onClick={() => { onPlaceId(item.place_id); setPicked(item); setItems([]); setSearched(false); }}>この地点を選択</button>
        <Attribution item={item} />
      </div>)}</div>}
    </details>}
    {placeId && <div className="order-field-hint">Google Mapsの地点を紐付け済み。今後の公共交通の経路検索に使用します。{!disabled && <button type="button" className="btn btn-ghost" onClick={() => { onPlaceId(""); setPicked(null); }}>地点の紐付けを解除</button>}</div>}
    {picked && <div className="google-place-results"><span className="google-maps-attribution" translate="no">Google Maps</span><p>{picked.name}<br />{picked.address}</p><Attribution item={picked} /><p className="order-field-hint">Googleの検索結果は確認用です。依頼書に残す住所は、主催者から確認した住所を登録してください。</p></div>}
  </div>;
}
