import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';

import { AuthService } from '../auth/auth.service';

interface HealthResponse {
  status: string;
  service: string;
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

  ngOnInit(): void {
    // このリクエストには MsalInterceptor が Bearer トークンを付与する（→ B-04）。
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (res) => this.apiStatus.set(`${res.status} (${res.service})`),
      error: () => this.apiStatus.set('未接続'),
    });
  }

  protected signOut(): void {
    this.auth.logout();
  }
}
