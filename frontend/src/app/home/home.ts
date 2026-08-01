import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { ProductService, ProductSummary } from '../products/product.service';

interface HealthResponse {
  status: string;
  service: string;
}

/** `GET /api/me` の応答（B-10）。API がトークンを検証し、所属一覧まで返す。 */
interface MeResponse {
  oid: string;
  displayName: string | null;
  isGuest: boolean;
  products: ProductSummary[];
}

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomePage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly products = inject(ProductService);

  /** サインイン中ユーザーの表示名（ルートガード通過後なので必ず存在する）。 */
  protected readonly displayName = this.auth.displayName;

  protected readonly apiStatus = signal<string>('確認中…');

  /**
   * API がトークンを検証して返した `oid`（B-04「端から端まで通ったことの可視化」）。
   * フロントが持つクレームではなく、サーバーが署名・aud・iss・scp を確かめた値。
   */
  protected readonly verifiedOid = signal<string>('確認中…');

  /** 所属プロダクト一覧と選択状態（B-10）。productId はサーバー由来でハードコードしない。 */
  protected readonly productList = this.products.products;
  protected readonly selectedProduct = this.products.selected;
  protected readonly hasProducts = this.products.hasProducts;
  protected readonly selectedProductId = computed(() => this.selectedProduct()?.productId ?? '');

  ngOnInit(): void {
    // どちらのリクエストにも MsalInterceptor が Bearer トークンを付与する（→ B-04）。
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (res) => this.apiStatus.set(`${res.status} (${res.service})`),
      error: () => this.apiStatus.set('未接続'),
    });

    // /api/me は認証必須。トークンが V-1〜V-4 を通れば oid と所属一覧が返る（B-04・B-10）。
    // 初回サインインならサーバー側で user とサンドボックス member が作られている（D-21）。
    this.http.get<MeResponse>('/api/me').subscribe({
      next: (res) => {
        this.verifiedOid.set(res.oid);
        this.products.setProducts(res.products);
      },
      error: () => this.verifiedOid.set('検証できませんでした'),
    });
  }

  /** セレクタでプロダクトを切り替える（2画面原則は維持。切替はシェルの操作）。 */
  protected onSelectProduct(event: Event): void {
    this.products.select((event.target as HTMLSelectElement).value);
  }

  protected signOut(): void {
    this.auth.logout();
  }
}
