"""Operation specs for CPA and CallTracking domains."""

from __future__ import annotations

from avito.core import BinaryResponse, OperationSpec
from avito.cpa.models import (
    CallTrackingCallResponse,
    CallTrackingCallsRequest,
    CallTrackingCallsResult,
    CallTrackingGetCallByIdRequest,
    CpaActionResult,
    CpaBalanceInfo,
    CpaBalanceInfoRequest,
    CpaCallByIdRequest,
    CpaCallComplaintRequest,
    CpaCallInfo,
    CpaCallsByTimeRequest,
    CpaCallsResult,
    CpaChatInfo,
    CpaChatsByTimeRequest,
    CpaChatsResult,
    CpaLeadComplaintRequest,
    CpaPhonesFromChatsRequest,
    CpaPhonesResult,
)

CPA_HEADERS = {"X-Source": "avito-py"}

GET_CPA_CHAT_BY_ACTION_ID = OperationSpec(
    name="cpa.chats.get_by_action_id",
    method="GET",
    path="/cpa/v1/chatByActionId/{actionId}",
    response_model=CpaChatInfo,
)
LIST_CPA_CHATS_CLASSIC = OperationSpec(
    name="cpa.chats.list_by_time_classic",
    method="POST",
    path="/cpa/v1/chatsByTime",
    request_model=CpaChatsByTimeRequest,
    response_model=CpaChatsResult,
    retry_mode="enabled",
)
LIST_CPA_CHATS = OperationSpec(
    name="cpa.chats.list_by_time",
    method="POST",
    path="/cpa/v2/chatsByTime",
    request_model=CpaChatsByTimeRequest,
    response_model=CpaChatsResult,
    retry_mode="enabled",
)
GET_CPA_PHONES_INFO = OperationSpec(
    name="cpa.chats.get_phones_info",
    method="POST",
    path="/cpa/v1/phonesInfoFromChats",
    request_model=CpaPhonesFromChatsRequest,
    response_model=CpaPhonesResult,
    retry_mode="enabled",
)
LIST_CPA_CALLS = OperationSpec(
    name="cpa.calls.list_by_time",
    method="POST",
    path="/cpa/v2/callsByTime",
    request_model=CpaCallsByTimeRequest,
    response_model=CpaCallsResult,
    retry_mode="enabled",
)
CREATE_CPA_CALL_COMPLAINT = OperationSpec(
    name="cpa.calls.create_complaint",
    method="POST",
    path="/cpa/v1/createComplaint",
    request_model=CpaCallComplaintRequest,
    response_model=CpaActionResult,
    retry_mode="enabled",
)
CREATE_CPA_LEAD_COMPLAINT = OperationSpec(
    name="cpa.leads.create_complaint_by_action_id",
    method="POST",
    path="/cpa/v1/createComplaintByActionId",
    request_model=CpaLeadComplaintRequest,
    response_model=CpaActionResult,
    retry_mode="enabled",
)
GET_CPA_BALANCE = OperationSpec(
    name="cpa.leads.get_balance_info",
    method="POST",
    path="/cpa/v3/balanceInfo",
    request_model=CpaBalanceInfoRequest,
    response_model=CpaBalanceInfo,
    retry_mode="enabled",
)
GET_CPA_ARCHIVE_RECORD: OperationSpec[BinaryResponse] = OperationSpec(
    name="cpa.archive.get_record",
    method="GET",
    path="/cpa/v1/call/{call_id}",
    response_kind="binary",
)
GET_CPA_ARCHIVE_BALANCE = OperationSpec(
    name="cpa.archive.get_balance_info",
    method="POST",
    path="/cpa/v2/balanceInfo",
    request_model=CpaBalanceInfoRequest,
    response_model=CpaBalanceInfo,
    retry_mode="enabled",
)
GET_CPA_ARCHIVE_CALL_BY_ID = OperationSpec(
    name="cpa.archive.get_call_by_id",
    method="POST",
    path="/cpa/v2/callById",
    request_model=CpaCallByIdRequest,
    response_model=CpaCallInfo,
    retry_mode="enabled",
)
GET_CALLTRACKING_CALL_BY_ID = OperationSpec(
    name="cpa.calltracking.get_call_by_id",
    method="POST",
    path="/calltracking/v1/getCallById/",
    request_model=CallTrackingGetCallByIdRequest,
    response_model=CallTrackingCallResponse,
    retry_mode="enabled",
)
GET_CALLTRACKING_CALLS = OperationSpec(
    name="cpa.calltracking.get_calls",
    method="POST",
    path="/calltracking/v1/getCalls/",
    request_model=CallTrackingCallsRequest,
    response_model=CallTrackingCallsResult,
    retry_mode="enabled",
)
GET_CALLTRACKING_RECORD: OperationSpec[BinaryResponse] = OperationSpec(
    name="cpa.calltracking.get_record_by_call_id",
    method="GET",
    path="/calltracking/v1/getRecordByCallId/",
    response_kind="binary",
)

__all__ = (
    "CPA_HEADERS",
    "CREATE_CPA_CALL_COMPLAINT",
    "CREATE_CPA_LEAD_COMPLAINT",
    "GET_CALLTRACKING_CALLS",
    "GET_CALLTRACKING_CALL_BY_ID",
    "GET_CALLTRACKING_RECORD",
    "GET_CPA_ARCHIVE_BALANCE",
    "GET_CPA_ARCHIVE_CALL_BY_ID",
    "GET_CPA_ARCHIVE_RECORD",
    "GET_CPA_BALANCE",
    "GET_CPA_CHAT_BY_ACTION_ID",
    "GET_CPA_PHONES_INFO",
    "LIST_CPA_CALLS",
    "LIST_CPA_CHATS",
    "LIST_CPA_CHATS_CLASSIC",
)
