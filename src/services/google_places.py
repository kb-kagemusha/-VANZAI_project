"""Explicit, authenticated Google place search. No response/address cache or key disclosure."""
import json
import os
import urllib.error
import urllib.request
from src.services.order_request_service import OrderRequestError

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"


def configured():
    return bool(os.getenv("GOOGLE_MAPS_API_KEY", "").strip())


def search_places(query):
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise OrderRequestError(503, "Google Mapsの住所検索が未設定です。API設定後に利用できます。")
    request = urllib.request.Request(SEARCH_URL, data=json.dumps({"textQuery": query, "languageCode": "ja", "regionCode": "JP", "pageSize": 5}).encode(),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.googleMapsUri,places.attributions"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read(131072))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        raise OrderRequestError(502, "Google Mapsから所在地を取得できませんでした。API設定を確認して再検索してください。") from None
    if not isinstance(data, dict) or not isinstance(data.get("places", []), list):
        raise OrderRequestError(502, "Google Mapsの検索結果を取得できませんでした。")
    results = []
    for place in data.get("places", [])[:5]:
        if not isinstance(place, dict) or not isinstance(place.get("id"), str):
            continue
        name = place.get("displayName") if isinstance(place.get("displayName"), dict) else {}
        def string(value):
            return value if isinstance(value, str) else ""
        attributions = place.get("attributions", [])
        results.append({"place_id": place["id"], "name": string(name.get("text")), "address": string(place.get("formattedAddress")), "maps_url": string(place.get("googleMapsUri")), "attributions": [{"provider": string(a.get("provider")), "providerUri": string(a.get("providerUri"))} for a in attributions if isinstance(a, dict)] if isinstance(attributions, list) else []})
    return results
