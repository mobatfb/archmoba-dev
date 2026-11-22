#pragma once
#include <ntddk.h>
#include <wdf.h>
#include <vhf.h>
#include <hidport.h>
#include <ntstrsafe.h>

// PROTOTIPO NO VALIDADO en WDK. No distribuir sin compilar, firmar y probar.
#define FUTJOY_MAX_SLOT 8
#define FUTJOY_REPORT_ID 1
#define FUTJOY_VENDOR_ID 0xF7A0 /* SOLO desarrollo: sustituir por VID autorizado */
#define FUTJOY_PRODUCT_BASE 0x2100
#define FUTJOY_IOCTL_SET_STATE CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_WRITE_DATA)
#define FUTJOY_IOCTL_NEUTRAL CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_WRITE_DATA)
#pragma pack(push,1)
typedef struct _FUTJOY_STATE { SHORT X; SHORT Y; USHORT Buttons; } FUTJOY_STATE;
typedef struct _FUTJOY_REPORT { UCHAR ReportId; SHORT X; SHORT Y; USHORT Buttons; } FUTJOY_REPORT;
#pragma pack(pop)
typedef struct _FUTJOY_CONTEXT {
    VHFHANDLE VhfHandle;
    ULONG Slot;
    WCHAR InstanceId[16];
} FUTJOY_CONTEXT, *PFUTJOY_CONTEXT;
WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(FUTJOY_CONTEXT, FutJoyContext);
DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD FutJoyDeviceAdd;
EVT_WDF_OBJECT_CONTEXT_CLEANUP FutJoyCleanup;
EVT_WDF_FILE_CLEANUP FutJoyFileCleanup;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL FutJoyIoctl;
