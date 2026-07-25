import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';

import { AuthService } from '../auth/auth.service';

interface HealthResponse {
  status: string;
  service: string;
}

/** `GET /api/me` の応答。API がトークンを検証して返す（B-04）。 */
interface MeResponse {
  oid: string;
  displayName: string | null;
}

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomePage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  /** サインイン中ユーザーの表示名（ルートガード通過後なので必ず存在する）。 */
  protected readonly displayName = this.auth.displayName;

  protected readonly apiStatus = signal<string>('確認中…');

  /**
   * API がトークンを検証して返した `oid`（B-04「端から端まで通ったことの可視化」）。
   * フロントが持つクレームではなく、サーバーが署名・aud・iss・scp を確かめた値。
   */
  protected readonly verifiedOid = signal<string>('確認中…');

  ngOnInit(): void {
    // どちらのリクエストにも MsalInterceptor が Bearer トークンを付与する（→ B-04）。
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (res) => this.apiStatus.set(`${res.status} (${res.service})`),
      error: () => this.apiStatus.set('未接続'),
    });

    // /api/me は認証必須。トークンが V-1〜V-4 を通れば oid が返る（B-04）。
    this.http.get<MeResponse>('/api/me').subscribe({
      next: (res) => this.verifiedOid.set(res.oid),
      error: () => this.verifiedOid.set('検証できませんでした'),
    });
  }

  protected signOut(): void {
    this.auth.logout();
  }
}
