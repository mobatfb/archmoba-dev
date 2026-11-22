/* FUTUREO VJOY - KMDF/VHF experimental gamepad prototype.
 * Not compiled, signed or tested on Windows. Test ONLY on disposable VM.
 */
#include "FutJoy.h"

static UCHAR g_Descriptor[] = {
  0x05,0x01, 0x09,0x05, 0xA1,0x01, 0x85,FUTJOY_REPORT_ID,
  0x09,0x30, 0x09,0x31, 0x16,0x00,0x80, 0x26,0xFF,0x7F,
  0x75,0x10, 0x95,0x02, 0x81,0x02,
  0x05,0x09, 0x19,0x01, 0x29,0x10, 0x15,0x00, 0x25,0x01,
  0x75,0x01, 0x95,0x10, 0x81,0x02, 0xC0
};
static const WCHAR* g_HardwareIds[8] = {
  L"ROOT\\FUTJOY01", L"ROOT\\FUTJOY02", L"ROOT\\FUTJOY03", L"ROOT\\FUTJOY04",
  L"ROOT\\FUTJOY05", L"ROOT\\FUTJOY06", L"ROOT\\FUTJOY07", L"ROOT\\FUTJOY08"
};
static ULONG GetSlot(WDFDEVICE device) {
  WCHAR ids[256]={0};
  ULONG actualSize=0;
  NTSTATUS status=WdfDeviceQueryProperty(device, DevicePropertyHardwareID,
                                          sizeof(ids),ids,&actualSize);
  if (!NT_SUCCESS(status)) return 0;
  UNICODE_STRING actual;
  RtlInitUnicodeString(&actual,ids);
  for (ULONG i=0;i<FUTJOY_MAX_SLOT;i++) {
    UNICODE_STRING candidate;
    RtlInitUnicodeString(&candidate,g_HardwareIds[i]);
    if (RtlEqualUnicodeString(&actual,&candidate,TRUE)) return i+1;
  }
  return 0;
}
static NTSTATUS SendState(PFUTJOY_CONTEXT ctx, const FUTJOY_STATE* state) {
  if (!ctx->VhfHandle) return STATUS_DEVICE_NOT_READY;
  FUTJOY_REPORT report={0};
  HID_XFER_PACKET packet={0};
  report.ReportId=FUTJOY_REPORT_ID;
  report.X=state->X;
  report.Y=state->Y;
  report.Buttons=state->Buttons;
  packet.reportBuffer=(PUCHAR)&report;
  packet.reportBufferLen=sizeof(report);
  packet.reportId=FUTJOY_REPORT_ID;
  return VhfReadReportSubmit(ctx->VhfHandle,&packet);
}
NTSTATUS DriverEntry(PDRIVER_OBJECT driver,PUNICODE_STRING registry) {
  WDF_DRIVER_CONFIG cfg;
  WDF_DRIVER_CONFIG_INIT(&cfg,FutJoyDeviceAdd);
  return WdfDriverCreate(driver,registry,WDF_NO_OBJECT_ATTRIBUTES,&cfg,WDF_NO_HANDLE);
}
VOID FutJoyCleanup(WDFOBJECT object) {
  PFUTJOY_CONTEXT ctx=FutJoyContext((WDFDEVICE)object);
  if (ctx->VhfHandle) {
    VhfDelete(ctx->VhfHandle,TRUE);
    ctx->VhfHandle=NULL;
  }
}
/* La finalizacion de un cliente (incluso si su proceso falla) restablece
 * todos los botones y centra los ejes. No requiere mensaje 'soltar'.
 * El control de reconexion de red sigue a cargo del anfitrion MULTIMANDO.
 */
VOID FutJoyFileCleanup(WDFFILEOBJECT fileObject) {
  WDFDEVICE device=WdfFileObjectGetDevice(fileObject);
  PFUTJOY_CONTEXT ctx=FutJoyContext(device);
  FUTJOY_STATE neutral={0};
  if (ctx->VhfHandle) {
    (void)SendState(ctx,&neutral);
  }
}

NTSTATUS FutJoyDeviceAdd(WDFDRIVER driver,PWDFDEVICE_INIT init) {
  UNREFERENCED_PARAMETER(driver);
  WDFDEVICE device;
  WDF_OBJECT_ATTRIBUTES attr;
  /* El driver recibe EvtFileCleanup tambien si el proceso termina sin
   * enviar una liberacion explicita de teclas. */
  WDF_FILEOBJECT_CONFIG fileCfg;
  WDF_FILEOBJECT_CONFIG_INIT(&fileCfg,NULL,NULL,FutJoyFileCleanup);
  WdfDeviceInitSetFileObjectConfig(init,&fileCfg,WDF_NO_OBJECT_ATTRIBUTES);
  WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attr,FUTJOY_CONTEXT);
  attr.EvtCleanupCallback=FutJoyCleanup;
  NTSTATUS status=WdfDeviceCreate(&init,&attr,&device);
  if (!NT_SUCCESS(status)) return status;
  PFUTJOY_CONTEXT ctx=FutJoyContext(device);
  ctx->VhfHandle=NULL;
  ctx->Slot=GetSlot(device);
  if (ctx->Slot<1 || ctx->Slot>8) return STATUS_NO_SUCH_DEVICE;
  WDF_IO_QUEUE_CONFIG queueCfg;
  WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueCfg,WdfIoQueueDispatchSequential);
  queueCfg.EvtIoDeviceControl=FutJoyIoctl;
  status=WdfIoQueueCreate(device,&queueCfg,WDF_NO_OBJECT_ATTRIBUTES,WDF_NO_HANDLE);
  if (!NT_SUCCESS(status)) return status;
  WCHAR path[64]={0};
  status=RtlStringCchPrintfW(path,RTL_NUMBER_OF(path),L"\\DosDevices\\FUTJOY%lu",ctx->Slot);
  if (!NT_SUCCESS(status)) return status;
  UNICODE_STRING symLink;
  RtlInitUnicodeString(&symLink,path);
  status=WdfDeviceCreateSymbolicLink(device,&symLink);
  if (!NT_SUCCESS(status)) return status;
  status=RtlStringCchPrintfW(ctx->InstanceId,RTL_NUMBER_OF(ctx->InstanceId),
                             L"FUTJOY%lu",ctx->Slot);
  if (!NT_SUCCESS(status)) return status;
  VHF_CONFIG vhf;
  VHF_CONFIG_INIT(&vhf,WdfDeviceWdmGetDeviceObject(device),
                  sizeof(g_Descriptor),g_Descriptor);
  vhf.VendorID=FUTJOY_VENDOR_ID;
  vhf.ProductID=(USHORT)(FUTJOY_PRODUCT_BASE+ctx->Slot);
  vhf.VersionNumber=0x0100;
  size_t chars=0;
  status=RtlStringCchLengthW(ctx->InstanceId,RTL_NUMBER_OF(ctx->InstanceId),&chars);
  if (!NT_SUCCESS(status)) return status;
  vhf.InstanceID=ctx->InstanceId;
  vhf.InstanceIDLength=(USHORT)((chars+1)*sizeof(WCHAR));
  status=VhfCreate(&vhf,&ctx->VhfHandle);
  if (!NT_SUCCESS(status)) return status;
  return VhfStart(ctx->VhfHandle);
}
VOID FutJoyIoctl(WDFQUEUE q,WDFREQUEST req,size_t outputLen,
                 size_t inputLen,ULONG code) {
  UNREFERENCED_PARAMETER(outputLen);
  PFUTJOY_CONTEXT ctx=FutJoyContext(WdfIoQueueGetDevice(q));
  NTSTATUS status=STATUS_INVALID_DEVICE_REQUEST;
  size_t consumed=0;
  FUTJOY_STATE neutral={0};
  if (code==FUTJOY_IOCTL_SET_STATE) {
    if (inputLen!=sizeof(FUTJOY_STATE)) status=STATUS_INVALID_BUFFER_SIZE;
    else {
      PVOID buffer=NULL;
      status=WdfRequestRetrieveInputBuffer(req,sizeof(FUTJOY_STATE),&buffer,NULL);
      if (NT_SUCCESS(status)) {
        status=SendState(ctx,(const FUTJOY_STATE*)buffer);
        if (NT_SUCCESS(status)) consumed=sizeof(FUTJOY_STATE);
      }
    }
  } else if (code==FUTJOY_IOCTL_NEUTRAL) {
    status=inputLen==0 ? SendState(ctx,&neutral) : STATUS_INVALID_BUFFER_SIZE;
  }
  WdfRequestCompleteWithInformation(req,status,consumed);
}
