import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminUserFilesComponent } from './admin-user-files.component';

describe('AdminUserFilesComponent', () => {
  let component: AdminUserFilesComponent;
  let fixture: ComponentFixture<AdminUserFilesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminUserFilesComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AdminUserFilesComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
