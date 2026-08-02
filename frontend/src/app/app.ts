import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AuthService } from './auth/auth.service';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  // E2E ビルドでは MSAL を配線しないため AuthService（→ MsalService）も注入しない。
  // ternary が短絡するので inject() 自体を呼ばず、DI 未提供による起動失敗を避ける
  // （EX-1・D-22）。本番／通常ビルドでは environment.e2e が静的に false で常に注入する。
  private readonly auth = environment.e2e ? null : inject(AuthService);

  protected readonly title = signal('Scrum Board');

  ngOnInit(): void {
    // E2E は認証をバックエンドの env ゲート resolver に委ねるため、フロントの
    // サインイン処理は何もしない。
    if (this.auth === null) {
      return;
    }
    // ① サインインのリダイレクトから戻ってきた応答をここで1度だけ処理する。
    // ② その完了後に、タブを開き直したケースの無音復元（ssoSilent）を試みる。
    //    順序が逆だと、リダイレクト直後にアカウントが二重処理されうる。
    this.auth.handleRedirect().subscribe({
      complete: () => this.auth!.restoreSession(),
      error: (err) => {
        console.error('[auth] redirect handling failed', err);
        this.auth!.restoreSession();
      },
    });
  }
}
