import { TestBed } from '@angular/core/testing';

import { ProductService, ProductSummary } from './product.service';

const SANDBOX: ProductSummary = { productId: 'prd_sandbox', name: 'サンドボックス', role: 'member' };
const SCRUM: ProductSummary = { productId: 'prd_scrum_board', name: 'スクラムボード', role: 'admin' };

describe('ProductService', () => {
  let service: ProductService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({});
    service = TestBed.inject(ProductService);
  });

  afterEach(() => sessionStorage.clear());

  it('starts empty (no product hardcoded)', () => {
    expect(service.products()).toEqual([]);
    expect(service.selected()).toBeNull();
    expect(service.hasProducts()).toBe(false);
  });

  it('defaults the selection to the first product', () => {
    service.setProducts([SANDBOX, SCRUM]);
    expect(service.selected()).toEqual(SANDBOX);
    expect(service.hasProducts()).toBe(true);
  });

  it('switches to a product that exists in the list', () => {
    service.setProducts([SANDBOX, SCRUM]);
    service.select('prd_scrum_board');
    expect(service.selected()).toEqual(SCRUM);
  });

  it('ignores a selection outside the available list', () => {
    service.setProducts([SANDBOX]);
    service.select('prd_unknown');
    expect(service.selected()).toEqual(SANDBOX);
  });

  it('persists the selection within the session and restores it', () => {
    service.setProducts([SANDBOX, SCRUM]);
    service.select('prd_scrum_board');

    // 新しいインスタンス（再マウント相当）でも保存済み選択を復元する。
    const restored = new ProductService();
    restored.setProducts([SANDBOX, SCRUM]);
    expect(restored.selected()).toEqual(SCRUM);
  });

  it('falls back to the first product when the saved selection is gone', () => {
    service.setProducts([SANDBOX, SCRUM]);
    service.select('prd_scrum_board');

    // 保存済み prd_scrum_board が今の一覧に無い → 先頭へフォールバック（範囲外選択を残さない）。
    const restored = new ProductService();
    restored.setProducts([SANDBOX]);
    expect(restored.selected()).toEqual(SANDBOX);
  });

  it('re-clamps the selection when the product list changes', () => {
    service.setProducts([SANDBOX, SCRUM]);
    service.select('prd_scrum_board');
    // 一覧が縮んで選択中が消えたら先頭へ。
    service.setProducts([SANDBOX]);
    expect(service.selected()).toEqual(SANDBOX);
  });
});
