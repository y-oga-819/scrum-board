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
  AuthenticationResult,
  EventType,
  InteractionRequiredAuthError,
  InteractionStatus,
} from '@azure/msal-browser';
import { Observable, filter, tap } from 'rxjs';

import { LOGIN_SCOPES } from './auth.config';

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
   *
   * 返す Observable はリダイレクト応答の処理が済むと完了する。呼び出し側は
   * これの完了を待ってから {@link restoreSession} を呼ぶ（リダイレクト直後は
   * 既にアカウントが取れており、無音復元を先に走らせると二重処理になるため）。
   */
  handleRedirect(): Observable<AuthenticationResult | null> {
    this.watchAccountChanges();

    // サインインのリダイレクトから戻ってきたハッシュを処理する。
    // 購読は呼び出し側（App）が行う。二重に handleRedirectObservable を
    // 呼ばないよう、ここでは購読せず Observable を返すだけにする。
    return this.msal.handleRedirectObservable().pipe(
      tap((result) => {
        if (result?.account) {
          this.msal.instance.setActiveAccount(result.account);
        }
        this.syncActiveAccount();
      }),
      takeUntilDestroyed(this.destroyRef),
    );
  }

  /**
   * 起動時にサインイン状態を無音で復元する。
   *
   * トークンは sessionStorage 限定なのでタブを開き直すと消えるが、Entra 側の
   * ブラウザセッションはタブを跨いで生きている。それを使って対話なしで
   * トークンを取り直す（無音更新が効く「期間」は組織の Entra ポリシーに委ねる）。
   *
   * リダイレクト処理（{@link handleRedirect}）の**完了後**に呼ぶこと。
   */
  restoreSession(): void {
    // 既にアカウントがあれば復元済み。無駄な通信（ssoSilent）を避ける。
    const accounts = this.msal.instance.getAllAccounts();
    if (accounts.length > 0) {
      this.msal.instance.setActiveAccount(accounts[0]);
      this.syncActiveAccount();
      return;
    }

    // アカウントが無い＝タブを開き直したケース。Entra のブラウザセッションで
    // 無音サインインを試みる。スコープはガードと同一（LOGIN_SCOPES）。
    this.msal
      .ssoSilent({ scopes: [...LOGIN_SCOPES] })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          if (result.account) {
            this.msal.instance.setActiveAccount(result.account);
          }
          this.syncActiveAccount();
        },
        error: (err) => {
          if (err instanceof InteractionRequiredAuthError) {
            // 無音では復元できない（対話が必要）。エラーにはせず未サインインの
            // まま進める。ルートガードが通常どおりリダイレクトログインへ送る。
            return;
          }
          // それ以外は予期しない失敗。状態は未サインインのまま、ログだけ残す。
          console.error('[auth] silent sign-in failed', err);
        },
      });
  }

  /** リダイレクト方式でサインアウトする。 */
  logout(): void {
    this.msal.logoutRedirect({ account: this._account() ?? undefined });
  }

  /** ログイン成功・各インタラクションの完了に追従してアカウント状態を取り直す。 */
  private watchAccountChanges(): void {
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
