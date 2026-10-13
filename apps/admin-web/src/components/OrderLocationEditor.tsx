import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, getPlaceStatus, searchPlaces, type PlaceSearchItem } from "../lib/api/client";

function Attribution({ item }: { item: PlaceSearchItem }) {
  return <>{item.attributions.map((attribution, i) => <span key={i}>{attribution.providerUri && /^https:\/\//.test(attribution.providerUri) ? <a href={attribution.providerUri} target="_blank" rel="noopener noreferrer">{attribution.provider ?? "情報提供元"}</a> : attribution.provider ?? ""}</span>)}</>;
}

export function OrderLocationEditor({ disabled, venueName, address, placeId, onAddress, onPlaceId }: {
  disabled: boolean; venueName: string; address: string; placeId: string; onAddress: (address: string) => void; onPlaceId: (placeId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PlaceSearchItem[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
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
    <label className="order-field">所在地の登録住所<textarea rows={2} value={address} disabled={disabled} placeholder="〒231-0001 神奈川県横浜市中区新港1丁目1−1" onChange={(e) => onAddress(e.target.value)} /></label>
    <a href={mapsUrl} target="_blank" rel="noopener noreferrer">Google Mapsで会場・所在地を確認</a>
    {!disabled && <>
      <div className="order-location-search"><label className="order-field">Google Mapsの会場検索<input value={query} maxLength={200} onChange={(e) => { setQuery(e.target.value); setItems([]); setSearched(false); setError(""); inputVersion.current += 1; }} /></label>
        <button type="button" className="btn btn-ghost" disabled={!status.data?.configured || query.trim().length < 2 || search.isPending} onClick={() => search.mutate({ text: query.trim(), version: inputVersion.current })}>{search.isPending ? "検索中..." : "所在地を検索"}</button></div>
      {status.data?.configured === false && <p className="order-field-hint">Google Mapsの自動検索はAPI設定後に利用できます。現在はGoogle Mapsで会場を確認し、主催者から確認した住所を登録してください。</p>}
      {status.isError && <p className="form-error">住所検索の設定を確認できませんでした。</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {searched && !items.length && <p>該当する会場がありません。名称や地域を変えて検索してください。</p>}
      {items.length > 0 && <div className="google-place-results"><span className="google-maps-attribution" translate="no">Google Maps</span>{items.map((item) => <div className="google-place-result" key={item.place_id}><strong>{item.name}</strong><p>{item.address}</p>
        <button type="button" className="btn btn-ghost" onClick={() => { onPlaceId(item.place_id); setPicked(item); setItems([]); setSearched(false); }}>この地点を選択</button>
        <Attribution item={item} />
      </div>)}</div>}
    </>}
    {placeId && <div className="order-field-hint">Google Mapsの地点を紐付け済み。今後の公共交通の経路検索に使用します。{!disabled && <button type="button" className="btn btn-ghost" onClick={() => { onPlaceId(""); setPicked(null); }}>地点の紐付けを解除</button>}</div>}
    {picked && <div className="google-place-results"><span className="google-maps-attribution" translate="no">Google Maps</span><p>{picked.name}<br />{picked.address}</p><Attribution item={picked} /><p className="order-field-hint">Googleの検索結果は確認用です。依頼書に残す住所は、主催者から確認した住所を登録してください。</p></div>}
  </div>;
}
