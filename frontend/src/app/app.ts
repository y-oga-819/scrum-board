import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AuthService } from './auth/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly auth = inject(AuthService);

  protected readonly title = signal('Scrum Board');

  ngOnInit(): void {
    // ① サインインのリダイレクトから戻ってきた応答をここで1度だけ処理する。
    // ② その完了後に、タブを開き直したケースの無音復元（ssoSilent）を試みる。
    //    順序が逆だと、リダイレクト直後にアカウントが二重処理されうる。
    this.auth.handleRedirect().subscribe({
      complete: () => this.auth.restoreSession(),
      error: (err) => {
        console.error('[auth] redirect handling failed', err);
        this.auth.restoreSession();
      },
    });
  }
}
