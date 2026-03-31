"""
Kintone App164のフィールド設定を自動化するスクリプト
Seleniumを使用してブラウザ操作を自動化
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
import subprocess

SUBDOMAIN = "xtf5wpxp3gk2"
GUEST_SPACE_ID = "3"
APP_ID = "164"
LOGIN_URL = f"https://{SUBDOMAIN}.cybozu.com/login"
APP_SETTINGS_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/admin/app/flow?app={APP_ID}"

# 追加が必要なフィールド
REQUIRED_FIELDS = [
    {
        "code": "type_id",
        "label": "案件種別ID",
        "type": "SINGLE_LINE_TEXT",
        "required": True,
        "change_from_dropdown": True
    },
    {
        "code": "name",
        "label": "カテゴリ名",
        "type": "SINGLE_LINE_TEXT",
        "required": True,
        "change_from_dropdown": True
    },
    {
        "code": "category_level",
        "label": "カテゴリレベル",
        "type": "SINGLE_LINE_TEXT",
        "required": True,
        "is_new": True
    },
    {
        "code": "parent_major",
        "label": "親（大カテゴリ）",
        "type": "SINGLE_LINE_TEXT",
        "required": False,
        "is_new": True
    },
    {
        "code": "parent_middle",
        "label": "親（中カテゴリ）",
        "type": "SINGLE_LINE_TEXT",
        "required": False,
        "is_new": True
    }
]

def setup_driver():
    """Chromeドライバーを設定"""
    options = Options()
    # ヘッドレスモードは使わない（ログインが必要なため）
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver

def login_kintone(driver):
    """Kintoneにログイン"""
    print("\n[STEP 1] Kintoneにログイン...")
    print(f"  ブラウザを開きます: {LOGIN_URL}")
    print("  ⚠️ 手動でログインしてください（多要素認証がある場合）")
    
    driver.get(LOGIN_URL)
    
    # ログイン完了まで待機
    print("  ログインが完了したらEnterキーを押してください...")
    input()

def navigate_to_app_settings(driver):
    """アプリ設定画面に移動"""
    print("\n[STEP 2] アプリ設定画面に移動...")
    url = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/{APP_ID}/"
    driver.get(url)
    time.sleep(2)
    
    # 設定アイコンをクリック
    try:
        settings_btn = driver.find_element(By.CSS_SELECTOR, "button[title='アプリの設定']")
        settings_btn.click()
        time.sleep(1)
        
        # 「設定」をクリック
        settings_link = driver.find_element(By.LINK_TEXT, "設定")
        settings_link.click()
        time.sleep(2)
        
        # 「フォーム」をクリック
        form_link = driver.find_element(By.LINK_TEXT, "フォーム")
        form_link.click()
        time.sleep(2)
    except Exception as e:
        print(f"  ⚠️ 自動遷移失敗: {e}")
        print(f"  手動でフォーム設定画面に移動してください")
        print(f"  URL: https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/admin/app/form?app={APP_ID}")
        input("  準備ができたらEnterキーを押してください...")

def update_fields_manually(driver):
    """フィールド設定を手動ガイド"""
    print("\n[STEP 3] フィールド設定を確認...")
    print("\n以下の操作を手動で実行してください:\n")
    
    print("【既存フィールドの変更】")
    print("1. 'type_id' フィールドをクリック")
    print("   → フィールドタイプを「文字列（1行）」に変更")
    print("   → 「必須項目」にチェック")
    print("   → 保存")
    print()
    print("2. 'name' フィールドをクリック")
    print("   → フィールドタイプを「文字列（1行）」に変更")
    print("   → 「必須項目」にチェック")
    print("   → 保存")
    print()
    
    print("【新規フィールドの追加】")
    print("3. 右側のフィールド一覧から「文字列（1行）」をドラッグ&ドロップ")
    print("   → フィールドコード: category_level")
    print("   → フィールド名: カテゴリレベル")
    print("   → 必須項目: チェック")
    print("   → 保存")
    print()
    print("4. 「文字列（1行）」をドラッグ&ドロップ")
    print("   → フィールドコード: parent_major")
    print("   → フィールド名: 親（大カテゴリ）")
    print("   → 必須項目: チェックなし")
    print("   → 保存")
    print()
    print("5. 「文字列（1行）」をドラッグ&ドロップ")
    print("   → フィールドコード: parent_middle")
    print("   → フィールド名: 親（中カテゴリ）")
    print("   → 必須項目: チェックなし")
    print("   → 保存")
    print()
    
    print("6. 画面右上の「フォームを保存」ボタンをクリック")
    print()
    print("7. 「アプリを更新」ボタンをクリック")
    print()
    
    input("全ての設定が完了したらEnterキーを押してください...")

def main():
    print("=" * 70)
    print("Kintone App164 フィールド設定自動化")
    print("=" * 70)
    
    print("\n⚠️ このスクリプトは半自動です:")
    print("  - ブラウザを自動で開きます")
    print("  - ログインは手動で行ってください")
    print("  - フィールド設定は画面のガイドに従って手動で行ってください")
    print()
    input("準備ができたらEnterキーを押してください...")
    
    driver = None
    try:
        driver = setup_driver()
        login_kintone(driver)
        navigate_to_app_settings(driver)
        update_fields_manually(driver)
        
        print("\n" + "=" * 70)
        print("✅ フィールド設定完了!")
        print("=" * 70)
        print("\n次のステップ:")
        print("  python scripts/upload_project_types.py")
        print("  を実行してデータを登録してください")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("\nブラウザを閉じますか？ (y/n)")
            if input().lower() == 'y':
                driver.quit()

if __name__ == "__main__":
    main()
