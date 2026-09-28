// Copyright 2010-2021, Google Inc.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//     * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//     * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//     * Neither the name of Google Inc. nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#include "win32/tip/tip_display_attributes.h"

#include <windows.h>

#include <string_view>

#include "absl/base/nullability.h"
#include "base/win32/com.h"

namespace mozc {
namespace win32 {
namespace tsf {

namespace {

constexpr std::wstring_view kInputDescription =
    L"TextService Display Attribute Input";
constexpr TF_DISPLAYATTRIBUTE kInputAttribute = {
    {TF_CT_NONE, {}},  // text color
    {TF_CT_NONE, {}},  // background color
    TF_LS_DOT,         // underline style
    FALSE,             // underline boldness
    {TF_CT_NONE, {}},  // underline color
    TF_ATTR_INPUT      // attribute info
};

constexpr std::wstring_view kConvertedDescription =
    L"TextService Display Attribute Converted";
constexpr TF_DISPLAYATTRIBUTE kConvertedAttribute = {
    {TF_CT_NONE, {}},         // text color
    {TF_CT_NONE, {}},         // background color
    TF_LS_SOLID,              // underline style
    TRUE,                     // underline boldness
    {TF_CT_NONE, {}},         // underline color
    TF_ATTR_TARGET_CONVERTED  // attribute info
};

#ifdef GOOGLE_JAPANESE_INPUT_BUILD

// {DDF5CDBA-C3FF-4BAF-B817-CC9210FAD27E}
constexpr GUID kDisplayAttributeInput = {
    0xddf5cdba,
    0xc3ff,
    0x4baf,
    {0xb8, 0x17, 0xcc, 0x92, 0x10, 0xfa, 0xd2, 0x7e}};

// {F829C8C0-0EBB-4D29-BD2F-E413A944B7E4}
constexpr GUID kDisplayAttributeConverted = {
    0xf829c8c0,
    0x0ebb,
    0x4d29,
    {0xbd, 0x2f, 0xe4, 0x13, 0xa9, 0x44, 0xb7, 0xe4}};

#else  // GOOGLE_JAPANESE_INPUT_BUILD

// {E16D8A5B-95C7-48A2-B7E6-2D1A0F4C9B23}
constexpr GUID kDisplayAttributeInput = {
    0xe16d8a5b,
    0x95c7,
    0x48a2,
    {0xb7, 0xe6, 0x2d, 0x1a, 0x0f, 0x4c, 0x9b, 0x23}};

// {7C9E3D21-4A6B-4F9A-96E3-5B3D8C1F7A66}
constexpr GUID kDisplayAttributeConverted = {
    0x7c9e3d21,
    0x4a6b,
    0x4f9a,
    {0x96, 0xe3, 0x5b, 0x3d, 0x8c, 0x1f, 0x7a, 0x66}};

#endif  // !GOOGLE_JAPANESE_INPUT_BUILD

}  // namespace

TipDisplayAttribute::TipDisplayAttribute(const GUID& guid,
                                         const TF_DISPLAYATTRIBUTE& attribute,
                                         const std::wstring_view description)
    : guid_(guid),
      description_(description),
      attribute_(attribute),
      original_attribute_(attribute) {}

STDMETHODIMP TipDisplayAttribute::GetGUID(GUID* absl_nullable guid) {
  return SaveToOutParam(guid_, guid);
}

STDMETHODIMP
TipDisplayAttribute::GetDescription(BSTR* absl_nullable description) {
  return SaveToOutParam(MakeUniqueBSTR(description_), description);
}

STDMETHODIMP
TipDisplayAttribute::GetAttributeInfo(
    TF_DISPLAYATTRIBUTE* absl_nullable attribute) {
  return SaveToOutParam(attribute_, attribute);
}

STDMETHODIMP
TipDisplayAttribute::SetAttributeInfo(
    const TF_DISPLAYATTRIBUTE* absl_nullable attribute) {
  if (attribute == nullptr) {
    return E_INVALIDARG;
  }
  attribute_ = *attribute;
  return S_OK;
}

STDMETHODIMP TipDisplayAttribute::Reset() {
  attribute_ = original_attribute_;
  return S_OK;
}

TipDisplayAttributeInput::TipDisplayAttributeInput()
    : TipDisplayAttribute(kDisplayAttributeInput, kInputAttribute,
                          kInputDescription) {}

const GUID& TipDisplayAttributeInput::guid() { return kDisplayAttributeInput; }

TipDisplayAttributeConverted::TipDisplayAttributeConverted()
    : TipDisplayAttribute(kDisplayAttributeConverted, kConvertedAttribute,
                          kConvertedDescription) {}

const GUID& TipDisplayAttributeConverted::guid() {
  return kDisplayAttributeConverted;
}

}  // namespace tsf
}  // namespace win32
}  // namespace mozc
