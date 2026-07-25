/**
 * サインイン状態を1か所に閉じ込めるサービス。
 *
 * コンポーネントは MSAL を直接触らず、このサービス越しに「今のアカウント」と
 * 「サインアウト」だけを扱う。MSAL への依存をここに集約することで、
 *  - 画面側のテストは本サービスを差し替えるだけで済み、
 *  - サインインまわりの実装差し替え（将来のゲスト経路など）も局所化される。
 * （バックエンドの「ユーザー解決ポート」（D-21）のフロント版にあたる考え方。）
 */
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MsalBroadcastService, MsalService } from '@azure/msal-angular';
import {
  AccountInfo,
  EventType,
  InteractionStatus,
} from '@azure/msal-browser';
import { filter } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly msal = inject(MsalService);
  private readonly broadcast = inject(MsalBroadcastService);
  private readonly destroyRef = inject(DestroyRef);

  /** 現在アクティブなアカウント。未サインインなら null。 */
  private readonly _account = signal<AccountInfo | null>(null);
  readonly account = this._account.asReadonly();

  readonly isAuthenticated = computed(() => this._account() !== null);
  readonly displayName = computed(
    () => this._account()?.name ?? this._account()?.username ?? '',
  );

  /**
   * リダイレクト応答を処理し、アカウント状態の追従を始める。
   * ルート（App）の初期化から1度だけ呼ぶ。
   */
  handleRedirect(): void {
    // サインインのリダイレクトから戻ってきたハッシュを処理する。
    this.msal
      .handleRedirectObservable()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          if (result?.account) {
            this.msal.instance.setActiveAccount(result.account);
          }
          this.syncActiveAccount();
        },
        error: (err) => console.error('[auth] redirect handling failed', err),
      });

    // ログイン成功イベントでアクティブアカウントを確定させる。
    this.broadcast.msalSubject$
      .pipe(
        filter((msg) => msg.eventType === EventType.LOGIN_SUCCESS),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.syncActiveAccount());

    // 各インタラクションが落ち着くたびに状態を取り直す（サインアウト含む）。
    this.broadcast.inProgress$
      .pipe(
        filter((status) => status === InteractionStatus.None),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.syncActiveAccount());

    this.syncActiveAccount();
  }

  /** リダイレクト方式でサインアウトする。 */
  logout(): void {
    this.msal.logoutRedirect({ account: this._account() ?? undefined });
  }

  /** MSAL のキャッシュからアクティブアカウントを読み直し、signal に反映する。 */
  private syncActiveAccount(): void {
    const active = this.msal.instance.getActiveAccount();
    if (active) {
      this._account.set(active);
      return;
    }
    // アクティブ未設定でもアカウントが1つあればそれを採用する
    // （リロード直後など。単一チーム前提なので常に1アカウント）。
    const accounts = this.msal.instance.getAllAccounts();
    if (accounts.length > 0) {
      this.msal.instance.setActiveAccount(accounts[0]);
      this._account.set(accounts[0]);
    } else {
      this._account.set(null);
    }
  }
}
