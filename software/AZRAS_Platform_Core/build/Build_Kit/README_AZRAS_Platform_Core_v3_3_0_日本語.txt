AZRAS Platform Core v3.3.0
地域別独立Project JSON生成・最終修正版

Module 9
名称：地域別独立Project JSON生成

処理
- Module 0の基本地域以外の都市を登録
- 使用チェックされた都市だけを対象
- 基本Project JSONを複製
- 基本JSONと同じフォルダーへ派生JSONを保存
- 派生JSONには新しいproject_idを付与
- 後日、派生JSONだけを単独Projectとして利用可能

派生JSONで置き換えるModule 0情報
- 国
- 都市
- 所在地・住所
- 緯度
- 経度
- Google座標文字列
- structured common.location
- module_outputs.module0の所在地スナップショット

地域別に更新・追加する内容
- 気候区分の企画概算
- 年平均気温の企画概算
- 暖房度日・冷房度日
- 日射量
- PV発電量概算
- 暖房・冷房エネルギー概算
- 地域適合性
- 災害適応性
- 耐久性
- 材料・施工性
- 法規確認度
- データ信頼度

保存例
基本JSONと同じフォルダー
├─ AZRAS_Tokyo.json
├─ AZRAS_London.json
├─ AZRAS_Paris.json
└─ AZRAS_New_York.json

基本JSONにはgenerated_region_filesとして派生JSON一覧を保存します。

Module 10
名称：地域別Project JSON比較

- 「地域別Project JSONを読込・比較開始」で再読込
- Module 9が生成した同一フォルダー内のJSONを読込
- 各JSONのModule 0所在地、地域適合性、CO₂・エネルギー概算を比較
- JSONファイル名と保存先を表示
- レーダーチャートを表示

重要
地域気候、PV、冷暖房、法規、材料施工性等には企画比較用概算が含まれます。
各派生JSONは単独利用できますが、正式な建設費・修繕費・事業収支には
現地単価、賃料、税、保険、法規、気象ファイル等による再計算が必要です。

ビルド
START_BUILD_AZRAS_Platform_Core_v3_3_0_KEEP_WINDOW_OPEN.cmd
