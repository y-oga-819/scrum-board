/**
 * 所属プロダクトと「いま選択中のプロダクト」を1か所に閉じ込めるサービス（B-10・D-21）。
 *
 * productId は **サーバーが返す所属一覧（`GET /api/me` の `products`）が正**であり、
 * フロントにハードコードしない（D-21）。このサービスはその一覧と選択状態だけを持つ
 * 純粋な状態ホルダーで、HTTP は持たない（取得は呼び出し側＝ home が行い `setProducts`
 * で流し込む）。こうしておくと単体テストが MSAL にも HttpClient にも触れずに済む。
 *
 * セレクタは「画面」ではなくシェルの要素であり、プロダクトバックログとスプリントの
 * 2画面構成は壊さない（D-21「2画面原則は維持される」）。切り替えは URL を
 * `/api/products/{productId}/…` に載せ替えるだけで効く（D-20）。
 */
import { Injectable, computed, signal } from '@angular/core';

/** `GET /api/me` の `products[]` の1要素。 */
export interface ProductSummary {
  productId: string;
  name: string;
  role: string;
}

/** 選択の保存キー。タブ内で選択を保持し、画面遷移で選び直さずに済むようにする。 */
const STORAGE_KEY = 'scrum-board.selectedProductId';

@Injectable({ providedIn: 'root' })
export class ProductService {
  private readonly _products = signal<ProductSummary[]>([]);
  /** 所属プロダクト一覧（サーバー由来）。 */
  readonly products = this._products.asReadonly();

  private readonly _selectedId = signal<string | null>(null);

  /**
   * いま選択中のプロダクト。選択 id が一覧に無ければ先頭にフォールバックし、
   * 一覧が空なら null（＝どのプロダクトにも属していない。未招待ユーザーの判定）。
   */
  readonly selected = computed<ProductSummary | null>(() => {
    const list = this._products();
    const id = this._selectedId();
    return list.find((p) => p.productId === id) ?? list[0] ?? null;
  });

  readonly hasProducts = computed(() => this._products().length > 0);

  /**
   * 所属一覧を受け取り、選択状態を確定する。
   *
   * 保存済みの選択が今の一覧にまだ在れば復元し、無ければ先頭へ。**選択は必ず
   * サーバーの一覧の範囲に収める**（消えたプロダクトを選択したまま操作させない）。
   */
  setProducts(products: ProductSummary[]): void {
    this._products.set(products);
    const saved = this.readSaved();
    const stillValid = saved !== null && products.some((p) => p.productId === saved);
    this._selectedId.set(stillValid ? saved : (products[0]?.productId ?? null));
  }

  /** プロダクトを切り替える。一覧に無い id は無視する（範囲外選択を作らない）。 */
  select(productId: string): void {
    if (!this._products().some((p) => p.productId === productId)) {
      return;
    }
    this._selectedId.set(productId);
    this.writeSaved(productId);
  }

  private readSaved(): string | null {
    try {
      return sessionStorage.getItem(STORAGE_KEY);
    } catch {
      // sessionStorage が使えない環境（プライベートモード等）でも動作は続ける。
      return null;
    }
  }

  private writeSaved(productId: string): void {
    try {
      sessionStorage.setItem(STORAGE_KEY, productId);
    } catch {
      // 保存できなくても選択自体は signal に載っており、この操作には支障しない。
    }
  }
}
