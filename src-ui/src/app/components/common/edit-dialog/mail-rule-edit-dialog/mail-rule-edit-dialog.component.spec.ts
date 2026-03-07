import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
import {
  MailAction,
  MailMetadataCorrespondentOption,
  MailRuleConsumptionScope,
  MailRulePdfLayout,
} from 'src/app/data/mail-rule'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { NumberComponent } from '../../input/number/number.component'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { SwitchComponent } from '../../input/switch/switch.component'
import { TagsComponent } from '../../input/tags/tags.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import { MailRuleEditDialogComponent } from './mail-rule-edit-dialog.component'

describe('MailRuleEditDialogComponent', () => {
  let component: MailRuleEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<MailRuleEditDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        MailRuleEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PermissionsFormComponent,
        NumberComponent,
        TagsComponent,
        CheckComponent,
        SwitchComponent,
      ],
      providers: [
        NgbActiveModal,
        {
          provide: MailAccountService,
          useValue: {
            listAll: () => of([]),
          },
        },
        {
          provide: CorrespondentService,
          useValue: {
            listAll: () => of([]),
          },
        },
        {
          provide: DocumentTypeService,
          useValue: {
            listAll: () => of([]),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(MailRuleEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 99, username: 'user99' }
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should support optional fields', () => {
    expect(component.showCorrespondentField).toBeFalsy()
    component.objectForm
      .get('assign_correspondent_from')
      .setValue(MailMetadataCorrespondentOption.FromCustom)
    expect(component.showCorrespondentField).toBeTruthy()

    expect(component.showActionParamField).toBeFalsy()
    component.objectForm.get('action').setValue(MailAction.Move)
    expect(component.showActionParamField).toBeTruthy()
    component.objectForm.get('action').setValue('')
    expect(component.showActionParamField).toBeFalsy()
    component.objectForm.get('action').setValue(MailAction.Tag)
    expect(component.showActionParamField).toBeTruthy()

    // coverage of optional chaining
    component.objectForm = null
    expect(component.showCorrespondentField).toBeFalsy()
    expect(component.showActionParamField).toBeFalsy()
  })

  it('should expose the combined PDF attachment consumption option', () => {
    expect(component.consumptionScopeOptions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: MailRuleConsumptionScope.Attachments,
          name: 'Only process attachments',
        }),
        expect.objectContaining({
          id: MailRuleConsumptionScope.EmailOnly,
          name: 'Process message as .eml',
        }),
        expect.objectContaining({
          id: MailRuleConsumptionScope.Everything,
          name: 'Process message as .eml and attachments separately',
        }),
      ])
    )

    expect(component.consumptionScopeOptions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: MailRuleConsumptionScope.CombinedPdfAttachment,
          name: 'Merge Email with Attachment',
        }),
      ])
    )
  })

  it('should relabel PDF layout options for combined mode', () => {
    expect(component.pdfLayoutOptions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: MailRulePdfLayout.TextHtml,
          name: 'Text, then HTML',
        }),
      ])
    )

    component.objectForm
      .get('consumption_scope')
      .setValue(MailRuleConsumptionScope.CombinedPdfAttachment)

    expect(component.pdfLayoutOptions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: MailRulePdfLayout.TextHtml,
          name: 'Text, then HTML, then attachments',
        }),
        expect.objectContaining({
          id: MailRulePdfLayout.HtmlText,
          name: 'Attachments first, then HTML/Text',
        }),
        expect.objectContaining({
          id: MailRulePdfLayout.Default,
          name: 'System default',
        }),
      ])
    )
  })
})
